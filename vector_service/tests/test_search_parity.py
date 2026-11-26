import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from vector_service.models.api import IngestRequest, SearchRequest
from vector_service.services.document_index import DocumentIndex
from vector_service.storage import VectorStore
from vector_service.tests.test_document_index import FixtureEncoder, legacy_module


class SearchParityTests(unittest.TestCase):
    def test_fifty_bonds_twenty_queries(self):
        encoder = FixtureEncoder()
        bonds = [dict(secid=f"SEC{i:03}", isin=f"ISIN{i:03}") for i in range(50)]
        events = []
        expected_inputs = {bond["secid"]: [] for bond in bonds}
        for i in range(35):
            members = [b["secid"] for j, b in enumerate(bonds) if (i + j) % 17]
            text = " ".join(members) + (". купон 12%." if i % 2 else ". оферта.")
            event = dict(inn="123", event_key=f"event-{i}", pseudo_guid=f"guid-{i}",
                         source_index=i, event_name="Раскрытие", event_date="2025-06-01",
                         full_text=text, is_corrected_by_another_event=i % 3 == 0)
            events.append(event)
            for secid in members:
                expected_inputs[secid].append(dict(event, text=text))
        chunker = legacy_module("chunking_service").ChunkingService()
        retrieval = legacy_module("retrieval_engine").RetrievalEngine()
        ranking = legacy_module("ranking_engine").RankingEngine()
        builder = legacy_module("context_builder").ContextBuilder()
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            store = VectorStore(Path(tmp), 3, "fixture", "fixture")
            try:
                index = DocumentIndex(store, encoder)
                self.assertEqual(index.ingest(IngestRequest(inn="123", bonds=bonds, events=events)).model_dump()["indexed"], len(events))
                for secid, prepared in expected_inputs.items():
                    candidates = [encoder.embed_chunk(c) for c in chunker.chunk_events(prepared)]
                    for n in range(20):
                        query = ("купон" if n % 2 else "оферта") + f" по выпуску {n}"
                        ranked = ranking.rerank(retrieval.retrieve(candidates, [encoder.embed_query(query)]))
                        actual = index.search(SearchRequest(bond={"secid": secid}, queries=[query])).model_dump(mode="json")
                        self.assertEqual(len(actual["results"]), 30)
                        for ref, row in zip(ranked, actual["results"], strict=True):
                            self.assertEqual((ref.chunk.text, ref.chunk.source_id, ref.chunk.section),
                                             (row["text"], row["source_id"], row["event_name"]))
                            self.assertAlmostEqual(ref.score, row["score"], delta=1e-6)
                        self.assertEqual(actual["context"], builder.build([r.chunk for r in ranked]))
            finally:
                store.close()
