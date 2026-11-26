import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from vector_service.algorithms.embedding_service import EmbeddingService
from vector_service.models.api import BondInput, IngestRequest, SearchRequest
from vector_service.services.document_index import DocumentIndex, analyze, build_issue
from vector_service.storage import VectorStore


class FixtureEncoder(EmbeddingService):
    """Возвращает фиксированные векторы предложений для сравнения алгоритмов."""

    def _call_embedding_service(self, sentences):
        return {
            "dense_embeddings": [[1.0, float("купон" in s), float("оферт" in s)] for s in sentences],
            "lexical_weights": [{"1": 0.5, "2": float("купон" in s)} for s in sentences],
        }


def legacy_module(name):
    module = f"vector_service.algorithms.{name}_reference"
    directory = Path(__file__).resolve().parents[2] / "backend/app/services/vector_retrieval"
    spec = importlib.util.spec_from_file_location(module, directory / f"{name}.py")
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    return reference


class DocumentIndexTests(unittest.TestCase):
    def test_issuename_priority_and_series_variants(self):
        issue = build_issue(BondInput(secid="S1", isin="I1", secname="Эмитент об. сер. 01",
                                      issuename="Облигации серии 02"))
        self.assertEqual(issue.series, "01")
        self.assertEqual(issue.series_variants, ("01", "02"))
        self.assertEqual(analyze("В сообщении указана серия 02.", [issue]), [(issue, "series")])
        self.assertEqual(analyze("Облигации серии 02", [issue]), [(issue, "issuename")])

        fallback = build_issue(BondInput(secid="S2", isin="I2", secname="Эмитент",
                                         issuename="Облигации серии 05"))
        self.assertEqual(fallback.series, "05")
        self.assertEqual(fallback.series_variants, ("05",))

        same = build_issue(BondInput(secid="S3", isin="I3", secname="Эмитент об. сер. А15",
                                     issuename="Облигации серии а15"))
        self.assertEqual(same.series_variants, ("А15",))

    def test_ingestion_reopen_and_search(self):
        common = dict(inn="123", pseudo_guid="p", event_date="2025-05-01", event_name="Купон",
                      is_corrected_by_another_event=True)
        events = [
            dict(common, event_key="a", source_index=0, full_text="1. Общие сведения SEC1 REG2 2. Содержание сообщения купон 10%. Выплата завтра."),
            dict(common, event_key="b", source_index=1, full_text="У выпуска БО-19 оферта."),
            dict(common, event_key="c", source_index=2, full_text="Посторонний выпуск"),
            dict(common, event_key="d", source_index=3, full_text=""),
            dict(common, event_key="e", source_index=4, full_text="SEC1", inn="456"),
        ]
        bonds = [dict(secid="SEC1", isin="ISIN1", secname="Первый БО-19"),
                 dict(secid="SEC2", isin="ISIN2", reg_number="REG2", issuename="У ВЫПУСКА БО-19"), dict(secid="EMPTY", isin="EMPTY")]
        encoder = FixtureEncoder()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            def connect():
                return VectorStore(Path(tmp), 3, "fixture", "fixture")
            store = connect()
            try:
                stats = DocumentIndex(store, encoder).ingest(IngestRequest(inn="123", bonds=bonds, events=events)).model_dump()
                self.assertEqual(stats, dict(indexed=2, skipped_no_match=1, skipped_invalid=1, skipped_inn_mismatch=1))
                self.assertEqual(store.tables["event_chunks"].count_rows(), 2)
                self.assertEqual({(r["event_key"], r["bond_secid"], r["match_reason"]) for r in store.rows("bond_event_map")},
                                 {("a","SEC1","secid"), ("a","SEC2","reg_number"), ("b","SEC1","series"), ("b","SEC2","issuename")})
            finally:
                store.close()
            store = connect()
            try:
                index = DocumentIndex(store, encoder)
                queries = ["купон", "оферта"]
                actual = index.search(SearchRequest(bond={"isin": "ISIN1"}, queries=queries)).model_dump(mode="json")
                prepared = [dict(events[0], text="купон 10%. Выплата завтра."),
                            dict(events[1], text=events[1]["full_text"])]
                chunks = legacy_module("chunking_service").ChunkingService().chunk_events(prepared)
                candidates = [encoder.embed_chunk(c) for c in chunks]
                scored = legacy_module("retrieval_engine").RetrievalEngine().retrieve(
                    candidates, [encoder.embed_query(q) for q in queries])
                expected = legacy_module("ranking_engine").RankingEngine().rerank(scored)
                self.assertEqual(actual["context"], legacy_module("context_builder").ContextBuilder().build(
                    [s.chunk for s in expected]))
                self.assertEqual(len(actual["results"]), len(expected))
                for row, ref in zip(actual["results"], expected, strict=True):
                    self.assertEqual(row["text"], ref.chunk.text)
                    self.assertAlmostEqual(row["score"], ref.score, delta=1e-6)
                self.assertEqual(index.search(SearchRequest(bond={"secid":"EMPTY"}, queries=queries)).model_dump(mode="json")["status"], "ok")
                self.assertEqual(index.search(SearchRequest(bond={"secid":"UNKNOWN"}, queries=queries)).model_dump(mode="json")["status"], "not_indexed")
                self.assertEqual(index.search(SearchRequest(bond={"secid":"SEC1","series":"x"}, queries=queries)).model_dump(mode="json")["results"], [])
                with patch.object(encoder, "embed_chunk", side_effect=ValueError("Сбой модели")):
                    with self.assertRaises(ValueError):
                        index.ingest(IngestRequest(inn="123", bonds=bonds, events=[events[0]]))
                self.assertEqual(index.search(SearchRequest(bond={"secid":"SEC1"}, queries=queries)).model_dump(mode="json")["results"], actual["results"])
            finally:
                store.close()
