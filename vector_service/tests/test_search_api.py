import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from vector_service.main import app
from vector_service.tests.test_document_index import FixtureEncoder


class SearchApiTests(unittest.TestCase):
    def test_http_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"VECTOR_SERVICE_API_KEY":"secret", "VECTOR_DB_DIR":tmp, "VECTOR_MODEL_DIR":tmp}
            class Encoder(FixtureEncoder):
                def embed_query(self, query):
                    return [1.0] * 1024, {"1": 1.0}
            with patch.dict("os.environ", env), patch("vector_service.main.LocalBGE", return_value=Encoder()):
                with TestClient(app) as client:
                    query = {"bond":{"secid":"SEC"}, "queries":["купон"]}
                    headers = {"X-API-Key":"secret"}
                    self.assertEqual(client.get("/ready").status_code, 200)
                    self.assertEqual(client.post("/search", json=query).status_code, 401)
                    self.assertEqual(client.post("/search", json=query, headers=headers).status_code, 202)
                    event = dict(event_key="key", inn="123", pseudo_guid="guid", source_index=0,
                                 event_name="Купон", event_date="2025-01-01", full_text="SEC.",
                                 is_corrected_by_another_event=False)
                    batch = dict(inn="123", bonds=[dict(secid="SEC", isin="ISIN", issuename="Выпуск")], events=[event])
                    with patch.object(Encoder, "_call_embedding_service", lambda self, texts: {
                        "dense_embeddings": [[1.0] * 1024 for t in texts], "lexical_weights": [{} for t in texts]
                    }):
                        result = client.post("/index/events", json=batch, headers=headers)
                        self.assertEqual(result.status_code, 200, result.text)
                        self.assertEqual(result.json()["indexed"], 1)
                        self.assertEqual(client.post("/search", json=query, headers=headers).json()["results"][0]["event_key"], "key")
                    self.assertEqual(app.state.index.store.rows("bond_event_map")[0]["issuename"], "Выпуск")
                    for body, status in ((dict(query, queries=[]),400),(dict(query,provider="openrouter"),409)):
                        self.assertEqual(client.post("/search", json=body, headers=headers).status_code, status)
