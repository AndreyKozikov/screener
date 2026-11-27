"""Тесты нормализации статусов журнала обновлений."""

import unittest
from datetime import datetime, timedelta, timezone

from app.routers.data_updates import _normalize_row


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NormalizeRowTests(unittest.TestCase):
    def test_fresh_heartbeat_keeps_run_active(self) -> None:
        now = _utc_now_naive()
        row = {
            "status": "running",
            "started_at": now - timedelta(hours=2),
            "heartbeat_at": now - timedelta(seconds=30),
        }

        self.assertEqual(_normalize_row(row)["status"], "running")

    def test_old_heartbeat_marks_run_interrupted(self) -> None:
        now = _utc_now_naive()
        row = {
            "status": "running",
            "started_at": now,
            "heartbeat_at": now - timedelta(minutes=11),
        }

        normalized = _normalize_row(row)

        self.assertEqual(normalized["status"], "error")
        self.assertIn("прервано", normalized["error_message"])

    def test_missing_heartbeat_falls_back_to_started_at(self) -> None:
        now = _utc_now_naive()
        row = {
            "status": "running",
            "started_at": now - timedelta(seconds=10),
        }

        self.assertEqual(_normalize_row(row)["status"], "running")


if __name__ == "__main__":
    unittest.main()
