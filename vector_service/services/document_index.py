from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

import numpy as np

from ..algorithms.chunking_service import ChunkingService
from ..algorithms.context_builder import ContextBuilder
from ..models.api import BondInput, IngestRequest, IngestResult, SearchHit, SearchRequest, SearchResult
from ..algorithms.event_filter import (
    clean_event_text, event_matches_issuename, event_matches_reg_number, event_matches_secid, event_matches_series,
)
from ..algorithms.ranking_engine import RankingEngine
from ..algorithms.retrieval_engine import RetrievalEngine
from ..algorithms.series import extract_series


class InvalidCatalog(ValueError):
    """Некорректные реквизиты в каталоге эмитента."""


class InvalidSearch(ValueError):
    """Некорректные параметры поискового запроса."""


@dataclass(frozen=True)
class Issue:
    """Карточка бумаги каталога с сериями для хранения и сопоставления."""

    bond: BondInput
    series: str | None
    series_variants: tuple[str, ...]


def build_issue(bond: BondInput) -> Issue:
    """Формирует карточку бумаги с сериями из названия и наименования выпуска."""
    secname_series = extract_series(bond.secname)
    issuename_series = extract_series(bond.issuename)
    variants = []
    for value in (secname_series, issuename_series):
        if value and all(value.lower() != item.lower() for item in variants):
            variants.append(value)
    return Issue(bond, secname_series or issuename_series, tuple(variants))


def analyze(text, catalog):
    """Сопоставляет сырой текст со всеми бумагами, сохраняя приоритет причины."""
    matches = []
    for issue in catalog:
        if event_matches_secid(text, issue.bond.secid):
            reason = "secid"
        elif event_matches_reg_number(text, issue.bond.reg_number):
            reason = "reg_number"
        elif event_matches_issuename(text, issue.bond.issuename):
            reason = "issuename"
        elif any(event_matches_series(text, series) for series in issue.series_variants):
            reason = "series"
        else:
            continue
        matches.append((issue, reason))
    return matches


class DocumentIndex:
    def __init__(self, store, encoder):
        self.store = store
        self.encoder = encoder
        self.dim = store.dim

    def validate_vector(self, vector, sparse):
        if len(vector) != self.dim or not np.isfinite(vector).all():
            raise ValueError("Неверная размерность или нечисловые значения в плотном векторе")
        if not np.isfinite(list(sparse.values())).all():
            raise ValueError("Некорректные лексические веса")

    def ingest(self, payload: IngestRequest) -> IngestResult:
        catalog = {}
        for b in payload.bonds:
            if b.inn is not None and b.inn != payload.inn:
                raise InvalidCatalog("В каталоге есть бумага другого эмитента")
            secid = b.secid
            row = build_issue(b)
            if secid in catalog and catalog[secid] != row:
                raise InvalidCatalog(f"Противоречивые реквизиты бумаги {secid}")
            catalog[secid] = row
        self.store.mark_bonds(catalog)
        counts = IngestResult()
        for document in payload.events:
            if not document.full_text.strip():
                counts.skipped_invalid += 1
                continue
            if document.inn != payload.inn:
                counts.skipped_inn_mismatch += 1
                continue
            matches = analyze(document.full_text, catalog.values())
            if not matches:
                counts.skipped_no_match += 1
                continue
            event = document.model_dump(mode="json")
            chunk, = ChunkingService().chunk_events([{**event, "text": clean_event_text(event["full_text"])}])
            embedded = self.encoder.embed_chunk(chunk)
            sentences = self.encoder.split_into_sentences(chunk.text)
            for _, vec, sparse in zip(sentences, embedded.sentence_embeddings, embedded.lexical_weights, strict=True):
                self.validate_vector(vec, sparse)
            self.store.save_event(document, matches, embedded, sentences)
            counts.indexed += 1
        self.store.collect()
        self.store.optimize()
        return counts

    def ready(self):
        if not self.store.indexes_ready():
            return False
        self.validate_vector(*self.encoder.embed_query("готовность"))
        return True

    def rank(self, candidates, metadata, queries):
        if not candidates:
            return [], ""
        query_data = [self.encoder.embed_query(query) for query in queries]
        for dense, sparse in query_data:
            self.validate_vector(dense, sparse)
        scored = RetrievalEngine().retrieve(candidates, query_data, top_k=30, alpha=0.8)
        ranked = RankingEngine().rerank(scored)
        results = [SearchHit.model_validate({**metadata[id(sc.chunk)], "score": float(sc.score)}) for sc in ranked]
        return results, ContextBuilder().build([sc.chunk for sc in ranked])

    def search(self, payload: SearchRequest) -> SearchResult:
        if payload.provider != "local":
            raise InvalidSearch("Запрос несовместим с локальным индексом BGE-M3")
        started = monotonic()
        start = payload.start_date.isoformat() if payload.start_date else None
        with self.store.search_snapshot(payload.bond.model_dump(), start) as snapshot:
            identifier, secid, isin, known, candidates, metadata = snapshot
            results, context = self.rank(candidates, metadata, payload.queries)
            return SearchResult(request_id=payload.request_id or str(uuid4()), status="ok" if known else "not_indexed",
                                bond_secid=secid, bond_isin=isin, index_fingerprint=self.store.fingerprint,
                                snapshot_id=identifier, elapsed_ms=int(1000 * (monotonic() - started)),
                                results=results, context=context)
