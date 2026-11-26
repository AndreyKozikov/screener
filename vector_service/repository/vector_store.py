import hashlib
import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from threading import Condition, RLock
from uuid import uuid4

import lancedb
from lancedb.index import BTree
import pyarrow as pa
from filelock import FileLock

from ..algorithms.models import Chunk, EmbeddedChunk
from ..algorithms.datetime_utils import compute_event_years
from ..models.records import TABLE_MODELS, IndexMeta
from ..schema import INDEXES, schemas


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def literal(value):
    return "'" + value.replace("'", "''") + "'"


class VectorStore:
    def __init__(self, directory, dim, model_id, sparse_source, ttl=300):
        directory.mkdir(parents=True, exist_ok=True)
        self.owner = FileLock(directory / ".writer.lock", timeout=0, thread_local=False)
        self.owner.acquire()
        try:
            self.writer = RLock()
            self.catalog = Condition()
            self.readers = set()
            self.collecting = False
            self.dim = dim
            self.ttl = ttl
            self.last_optimize_at = None
            self.db = lancedb.connect(directory)
            if "bond_event_map" in self.db.list_tables().tables:
                links = self.db.open_table("bond_event_map")
                if "issuename" not in links.schema.names:
                    links.add_columns(pa.field("issuename", pa.string()))
            self.tables = {
                name: self.db.create_table(name, schema=schema, exist_ok=True)
                for name, schema in schemas(dim).items()
            }
            config = dict(embedding_dim=dim, model_id=model_id, sparse_source=sparse_source,
                          supports_sparse=True, alpha=0.8, series_source="secname",
                          sentence_splitter_version="1", text_pipeline_version="1",
                          series_extractor_version="1", commit_protocol_version="1", schema_version="1")
            self.fingerprint = digest(json.dumps(config, sort_keys=True))
            meta = self.rows("index_meta")
            if meta and meta[0]["fingerprint"] != self.fingerprint:
                raise ValueError("Конфигурация эмбеддингов отличается от сохранённого индекса")
            if not meta:
                self.add("index_meta", [{**config, "fingerprint": self.fingerprint,
                                         "built_at": now(), "catalog_epoch": 0}])
            for name, columns in INDEXES.items():
                table = self.tables[name]
                existing = {tuple(index.columns) for index in table.list_indices()}
                for column in columns:
                    if (column,) not in existing:
                        table.create_index(column, config=BTree())
        except BaseException:
            self.owner.release()
            raise

    def close(self):
        self.owner.release()

    def rows(self, name, predicate=None, columns=None):
        query = self.tables[name].search()
        if predicate:
            query = query.where(predicate, prefilter=True)
        if columns:
            query = query.select(columns)
        return query.limit(None).to_list()

    def by_keys(self, name, column, values):
        keys = sorted(set(values))
        result = []
        for offset in range(0, len(keys), 250):
            batch = ", ".join(map(literal, keys[offset:offset + 250]))
            result.extend(self.rows(name, f"{column} IN ({batch})"))
        return result

    def validated_table(self, name, records):
        model = TABLE_MODELS[name]
        values = [model.model_validate(row).model_dump(mode="json") for row in records]
        return pa.Table.from_pylist(values, schema=self.tables[name].schema)

    def add(self, name, records):
        self.tables[name].add(self.validated_table(name, records))

    def upsert(self, name, key, records):
        if records:
            table = self.tables[name]
            data = self.validated_table(name, records)
            table.merge_insert(key).when_matched_update_all().when_not_matched_insert_all().execute(data)

    def mark_bonds(self, secids):
        with self.writer:
            stamp = now()
            self.upsert("bond_index_state", "bond_secid", [
                {"bond_secid": secid, "indexed_at": stamp} for secid in set(secids)
            ])

    @contextmanager
    def snapshot(self, field, value):
        identifier = str(uuid4())
        with self.catalog:
            self.catalog.wait_for(lambda: not self.collecting)
            links = self.rows("bond_event_map", f"{field} = {literal(value)}")
            states = self.by_keys("event_state", "event_key", [r["event_key"] for r in links])
            pinned = {s["event_key"]: s["active_write_id"] for s in states if s["status"] == "active"}
            links = [r for r in links if pinned.get(r["event_key"]) == r["write_id"]]
            self.readers.add(identifier)
        try:
            yield identifier, links
        finally:
            with self.catalog:
                self.readers.remove(identifier)
                self.catalog.notify_all()

    def commit_state(self, event_key, version, status):
        with self.catalog:
            meta, = self.rows("index_meta")
            epoch = meta["catalog_epoch"] + 1
            meta = IndexMeta.model_validate({**meta, "catalog_epoch": epoch})
            self.tables["index_meta"].update(values={"catalog_epoch": meta.catalog_epoch})
            self.upsert("event_state", "event_key", [dict(event_key=event_key, active_write_id=version,
                        status=status, committed_at=now(), commit_seq=epoch)])

    def save_event(self, document, matches, embedded, sentences):
        links = [
            dict(bond_secid=issue.bond.secid, bond_isin=issue.bond.isin,
                 issuename=issue.bond.issuename, bond_reg_number=issue.bond.reg_number,
                 bond_series=issue.series, match_reason=reason,
                 bond_first_tradedate=issue.bond.first_tradedate.isoformat() if issue.bond.first_tradedate else None)
            for issue, reason in matches
        ]
        return self.replace(document.model_dump(mode="json"), links, embedded, sentences)

    def replace(self, event, matches, embedded, sentences):
        with self.writer:
            key = event["event_key"]
            bond_fields = ("bond_isin", "bond_reg_number", "bond_series", "bond_first_tradedate")
            known_links = self.by_keys("bond_event_map", "bond_secid", [m["bond_secid"] for m in matches])
            states = self.by_keys("event_state", "event_key", [r["event_key"] for r in known_links])
            active = {s["event_key"]: s["active_write_id"] for s in states if s["status"] == "active"}
            incoming = {m["bond_secid"]: m for m in matches}
            for link in known_links:
                if active.get(link["event_key"]) == link["write_id"]:
                    match = incoming[link["bond_secid"]]
                    if any(link[f] != match[f] for f in bond_fields):
                        raise ValueError(f"Изменились реквизиты бумаги {match['bond_secid']}")
            previous = self.by_keys("event_state", "event_key", [key])
            if previous and previous[0]["status"] == "active":
                old_key = f"{key}|{previous[0]['active_write_id']}"
                old, = self.by_keys("event_chunks", "event_write_key", [old_key])
                if any(old[f] != event[f] for f in ("event_date", "pseudo_guid", "is_corrected_by_another_event")):
                    raise ValueError(f"Изменились реквизиты события {key}")
            version = str(uuid4())
            chunk_id = digest(key)
            chunk_write_key = f"{chunk_id}|{version}"
            stamp = now()
            common = dict(event_key=key, chunk_id=chunk_id, write_id=version)
            event_fields = dict(event_date=event["event_date"], event_year=int(event["event_date"][:4]),
                                is_corrected_by_another_event=event["is_corrected_by_another_event"])
            vectors = []
            for i, (sentence, vector, sparse) in enumerate(zip(
                sentences, embedded.sentence_embeddings, embedded.lexical_weights, strict=True
            )):
                vectors.append(dict(**common, sentence_id=digest(f"{chunk_write_key}|{i}|{sentence}"),
                    chunk_write_key=chunk_write_key, sentence_index=i, sentence_text=sentence,
                    vector=vector, terms=list(sparse), weights=list(sparse.values()), created_at=stamp))
            if not vectors or not matches or len({m["bond_secid"] for m in matches}) != len(matches):
                raise ValueError("Неполная версия события или повторная связь с бумагой")
            links = [dict(**common, **event_fields, **m, source_index=event["source_index"],
                          bond_event_key=f"{m['bond_secid']}|{key}",
                          bond_event_write_key=f"{m['bond_secid']}|{key}|{version}",
                          chunk_write_key=chunk_write_key) for m in matches]
            chunks = [dict(**common, **event_fields, event_write_key=f"{key}|{version}",
                           pseudo_guid=event["pseudo_guid"], text=embedded.chunk.text, source_type="event",
                           source_id=embedded.chunk.source_id, event_name=embedded.chunk.section,
                           text_pipeline_version="1", created_at=stamp)]
            for table, records, column in (
                ("event_vectors", vectors, "chunk_write_key"),
                ("event_chunks", chunks, "event_write_key"),
                ("bond_event_map", links, "chunk_write_key"),
            ):
                self.add(table, records)
                if self.tables[table].count_rows(f"{column} = {literal(records[0][column])}") != len(records):
                    raise ValueError(f"Не удалось проверить запись в {table}")
            self.commit_state(key, version, "active")
            return version

    @contextmanager
    def exclusive_gc(self):
        with self.writer, self.catalog:
            self.collecting = True
            try:
                yield self.catalog.wait_for(lambda: not self.readers, timeout=self.ttl)
            finally:
                self.collecting = False
                self.catalog.notify_all()

    def collect(self):
        with self.exclusive_gc() as allowed:
            if not allowed:
                return False
            states = {row["event_key"]: row for row in self.rows("event_state")}
            for name in ("event_vectors", "event_chunks", "bond_event_map"):
                versions = {(r["event_key"], r["write_id"]) for r in self.rows(name, columns=["event_key", "write_id"])}
                for key, version in versions:
                    state = states.get(key, {})
                    if state.get("status") == "recovering" or (
                        state.get("status") == "active" and state["active_write_id"] == version
                    ):
                        continue
                    self.tables[name].delete(f"event_key = {literal(key)} AND write_id = {literal(version)}")
            return True

    def optimize(self):
        with self.exclusive_gc() as allowed:
            if not allowed:
                return False
            for table in self.tables.values():
                table.optimize(cleanup_older_than=timedelta(seconds=max(604800, self.ttl)))
            self.last_optimize_at = now()
            return True

    def indexes_ready(self):
        return all(table.index_stats(entry.name).num_unindexed_rows == 0
                   for table in self.tables.values() for entry in table.list_indices())

    @contextmanager
    def search_snapshot(self, bond, start_date):
        field = "bond_secid" if bond.get("secid") else "bond_isin"
        identifier = bond.get("secid") or bond["isin"]
        with self.snapshot(field, identifier) as (snapshot, links):
            secid = links[0]["bond_secid"] if links else identifier
            isin = links[0]["bond_isin"] if links else bond.get("isin")
            known = bool(links or self.by_keys("bond_index_state", "bond_secid", [secid]))
            floor = start_date or (links[0]["bond_first_tradedate"] if links else None)
            years = set(compute_event_years(floor)) if floor else None
            selected = [r for r in links if (years is None or r["event_year"] in years)
                        and all(bond.get(k) is None or bond[k] == r[c] for k, c in (
                            ("reg_number", "bond_reg_number"), ("series", "bond_series"), ("isin", "bond_isin")))]
            candidates, metadata = self.load_candidates(selected)
            yield snapshot, secid, isin, known, candidates, metadata

    def load_candidates(self, links):
        links.sort(key=lambda r: r["source_index"])
        links.sort(key=lambda r: r["event_date"], reverse=True)
        chunks = {r["event_write_key"]: r for r in self.by_keys(
            "event_chunks", "event_write_key", (f"{r['event_key']}|{r['write_id']}" for r in links)
        )}
        sentences = defaultdict(list)
        for row in self.by_keys("event_vectors", "chunk_write_key", (r["chunk_write_key"] for r in links)):
            sentences[row["chunk_write_key"]].append(row)
        candidates = []
        metadata = {}
        for link in links:
            row = chunks[f"{link['event_key']}|{link['write_id']}"]
            chunk = Chunk(row["text"], "event", row["source_id"], row["event_name"])
            vectors = sorted(sentences[link["chunk_write_key"]], key=lambda r: r["sentence_index"])
            if not vectors or [r["sentence_index"] for r in vectors] != list(range(len(vectors))):
                raise ValueError("Нарушена целостность векторов события")
            candidates.append(EmbeddedChunk(chunk, [r["vector"] for r in vectors],
                [dict(zip(r["terms"], r["weights"], strict=True)) for r in vectors]))
            metadata[id(chunk)] = row
        return candidates, metadata
