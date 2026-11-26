"""Тесты журналирования ручных обновлений данных."""

import unittest
from datetime import datetime

from app.services import data_update_journal as journal


class DataUpdateJournalTests(unittest.TestCase):
    def test_maps_known_update_paths(self) -> None:
        cases = {
            ("POST", "/update/bonds_data"): "bonds",
            ("POST", "/zerocupon/refresh"): "zerocupon",
            ("POST", "/rating/refresh"): "ratings",
            ("POST", "/emitents/update"): "emitents",
            ("POST", "/bonds/refresh-coupons"): "coupons",
            ("POST", "/currency/refresh"): "currency",
            ("POST", "/ruonia/refresh"): "ruonia",
            ("POST", "/keyrate/load"): "keyrate",
            ("GET", "/trading-history/download"): "trading-history",
            ("POST", "/forecast/upload"): "forecast",
            ("POST", "/ipc/upload"): "ipc",
            ("POST", "/ipc/upload_ipc_weekly"): "ipc-weekly",
            ("POST", "/inflations/upload"): "inflation-expectations",
            ("POST", "/inflations/upload_by_url"): "inflation-expectations",
            ("POST", "/inflations/upload_inflation_data"): "inflation",
            ("POST", "/inflations/upload_inflation_data_by_url"): "inflation",
        }
        for (method, path), expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(journal.resolve_update_task(method, path), expected)

    def test_does_not_map_single_bond_coupon_refresh(self) -> None:
        self.assertIsNone(
            journal.resolve_update_task("POST", "/bonds/RU000A0JQAM6/refresh-coupons")
        )

    def test_classifies_success_and_error_payloads(self) -> None:
        self.assertEqual(
            journal.classify_payload("bonds", {"status": "ok"}),
            ("success", None),
        )
        status, error = journal.classify_payload("bonds", {"status": "error", "error": "boom"})
        self.assertEqual(status, "error")
        self.assertIn("boom", error or "")
        status, error = journal.classify_payload("bonds", {"success": False, "message": "denied"})
        self.assertEqual(status, "error")
        self.assertIn("denied", error or "")

    def test_classifies_http_error(self) -> None:
        status, error, payload = journal.classify_response(
            "bonds",
            500,
            "application/json",
            b'{"detail":"source unavailable"}',
        )
        self.assertEqual(status, "error")
        self.assertIn("source unavailable", error or "")
        self.assertEqual(payload, {"detail": "source unavailable"})

    def test_partial_trading_history_is_error(self) -> None:
        status, error = journal.classify_payload("trading-history", {"updated": 3, "failed": 1})
        self.assertEqual(status, "error")
        self.assertIn("1", error or "")

    def test_build_log_contains_key_fields(self) -> None:
        started = datetime(2026, 11, 26, 12, 0, 0)
        log_text = journal.build_update_log(
            task_id="bonds",
            trigger=journal.TRIGGER_MANUAL,
            run_id="run-1",
            request_path="/update/bonds_data",
            request_query="force_update=true",
            started_at=started,
            finished_at=datetime(2026, 11, 26, 12, 0, 12),
            status="error",
            http_status=500,
            error_message="boom",
            payload={"detail": "boom"},
        )
        self.assertIn("START task=bonds", log_text)
        self.assertIn("REQUEST /update/bonds_data?force_update=true", log_text)
        self.assertIn("RESPONSE HTTP 500", log_text)
        self.assertIn("ERROR boom", log_text)
        self.assertIn("FINISH error", log_text)

    def test_safe_query_truncates_long_values(self) -> None:
        value = "a" * (journal.MAX_QUERY_CHARS + 50)
        self.assertEqual(len(journal.safe_query(value) or ""), journal.MAX_QUERY_CHARS)
        self.assertIsNone(journal.safe_query(""))


if __name__ == "__main__":
    unittest.main()
