import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vector_service.algorithms.models import Chunk, EmbeddedChunk
from vector_service.storage import VectorStore


class StoreTests(unittest.TestCase):
    def test_versions_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VectorStore(Path(tmp), 2, "test", "local-lexical-v1", ttl=0)
            try:
                event = dict(event_key="e", event_date="2025-01-01", pseudo_guid="g", source_index=0,
                             is_corrected_by_another_event=True)
                match = dict(bond_secid="SEC", bond_isin="ISIN", bond_series=None,
                             bond_reg_number=None, bond_first_tradedate=None, match_reason="secid")
                chunk = Chunk("Текст", "event", "event_2025-01-01", "Событие")
                embedded = EmbeddedChunk(chunk, [[1, 0]], [{"а": 1.0}])
                first = store.replace(event, [match], embedded, ["Текст"])
                with store.snapshot("bond_secid", "SEC") as (_, links):
                    second = store.replace(event, [match], embedded, ["Текст"])
                    self.assertNotEqual(first, second)
                    self.assertEqual(links[0]["write_id"], first)
                    self.assertFalse(store.collect())
                self.assertTrue(store.collect())
                self.assertEqual(store.rows("event_vectors")[0]["write_id"], second)
                with patch.object(store, "commit_state", side_effect=RuntimeError("Прерывание до commit")):
                    with self.assertRaises(RuntimeError):
                        store.replace(event, [match], embedded, ["Текст"])
                with store.snapshot("bond_secid", "SEC") as (_, links):
                    self.assertEqual([link["write_id"] for link in links], [second])
                self.assertTrue(store.collect())
                self.assertEqual(store.tables["event_vectors"].count_rows(), 1)
                self.assertTrue(store.optimize())
            finally:
                store.close()
