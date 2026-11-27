"""Тесты репозитория журнала запусков обновления данных."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from db_repository.repository.operations.data_update_runs_repository import (
    DataUpdateRunsRepository,
)
from db_repository.models.orm.data_update_run import DataUpdateRun  # noqa: F401


class DataUpdateRunsRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "bonds.db"
        engine = create_engine(f"sqlite:///{self.db_path}")
        SQLModel.metadata.create_all(engine)
        engine.dispose()
        self.repo = DataUpdateRunsRepository(db_path=self.db_path)

    def tearDown(self) -> None:
        self.repo.close()
        self._tmp.cleanup()

    def _run(
        self,
        run_id: str,
        task_id: str = "bonds",
        started_at: datetime | None = None,
        status: str = "success",
        *,
        trigger: str = "manual",
    ) -> None:
        started_at = started_at or datetime(2026, 11, 26, 12, 0, 0)
        self.repo.start_run(
            run_id=run_id,
            task_id=task_id,
            trigger=trigger,
            started_at=started_at,
            request_path=f"/{task_id}",
        )
        self.repo.finish_run(
            run_id=run_id,
            task_id=task_id,
            trigger=trigger,
            started_at=started_at,
            status=status,
            finished_at=started_at + timedelta(seconds=10),
            duration_ms=10_000,
            log_text=f"log {run_id}",
        )

    def test_start_and_finish_run(self) -> None:
        started_at = datetime(2026, 11, 26, 12, 0, 0)
        created = self.repo.start_run(
            run_id="run-1",
            task_id="bonds",
            trigger="manual",
            started_at=started_at,
            request_path="/update/bonds_data",
        )
        self.assertEqual(created["status"], "running")

        finished = self.repo.finish_run(
            run_id="run-1",
            status="success",
            finished_at=started_at + timedelta(seconds=15),
            duration_ms=15_000,
            log_text="ok",
        )
        self.assertEqual(finished["status"], "success")
        self.assertEqual(finished["duration_ms"], 15_000)
        self.assertEqual(finished["log_text"], "ok")

    def test_finish_run_creates_missing_row(self) -> None:
        started_at = datetime(2026, 11, 26, 12, 0, 0)
        finished = self.repo.finish_run(
            run_id="run-missing-start",
            task_id="ipc",
            trigger="scheduled",
            started_at=started_at,
            status="error",
            finished_at=started_at + timedelta(seconds=4),
            error_message="failed",
            log_text="error log",
        )
        self.assertEqual(finished["task_id"], "ipc")
        self.assertEqual(finished["status"], "error")
        self.assertEqual(finished["trigger"], "scheduled")

    def test_finish_run_stores_warning_for_success(self) -> None:
        started_at = datetime(2026, 11, 27, 3, 46, 16)
        self.repo.start_run(
            run_id="run-warning",
            task_id="trading-history",
            trigger="manual",
            started_at=started_at,
        )
        finished = self.repo.finish_run(
            run_id="run-warning",
            status="success",
            finished_at=started_at + timedelta(seconds=30),
            warning_message="Не обновлены данные по 2 из 3283 инструментов",
            log_text="warning log",
        )
        self.assertEqual(finished["status"], "success")
        self.assertEqual(
            finished["warning_message"],
            "Не обновлены данные по 2 из 3283 инструментов",
        )
        self.assertIsNone(finished["error_message"])

    def test_get_latest_runs_returns_one_row_per_task(self) -> None:
        self._run("a-1", "bonds", datetime(2026, 11, 26, 10, 0, 0))
        self._run("a-2", "bonds", datetime(2026, 11, 26, 11, 0, 0), "error")
        self._run("b-1", "ipc", datetime(2026, 11, 26, 9, 0, 0))

        latest = {row["task_id"]: row for row in self.repo.get_latest_runs()}
        self.assertEqual(latest["bonds"]["run_id"], "a-2")
        self.assertEqual(latest["bonds"]["status"], "error")
        self.assertEqual(latest["ipc"]["run_id"], "b-1")

    def test_get_run_returns_none_for_unknown_id(self) -> None:
        self.assertIsNone(self.repo.get_run("missing"))

    def test_try_start_run_blocks_second_update(self) -> None:
        started_at = datetime(2026, 11, 27, 5, 0, 0)
        self.assertTrue(
            self.repo.try_start_run(
                run_id="run-1",
                task_id="coupons",
                trigger="scheduled",
                started_at=started_at,
            )
        )
        self.assertFalse(
            self.repo.try_start_run(
                run_id="run-2",
                task_id="bonds",
                trigger="manual",
                started_at=started_at + timedelta(seconds=1),
                stale_before=started_at - timedelta(seconds=1),
            )
        )

        self.repo.finish_run(
            run_id="run-1",
            status="success",
            finished_at=started_at + timedelta(seconds=10),
            log_text="ok",
        )
        self.assertTrue(
            self.repo.try_start_run(
                run_id="run-3",
                task_id="bonds",
                trigger="manual",
                started_at=started_at + timedelta(seconds=20),
            )
        )

    def test_try_start_run_ignores_stale_running(self) -> None:
        started_at = datetime(2026, 11, 27, 0, 0, 0)
        self.assertTrue(
            self.repo.try_start_run(
                run_id="run-old",
                task_id="coupons",
                trigger="scheduled",
                started_at=started_at,
            )
        )
        self.assertTrue(
            self.repo.try_start_run(
                run_id="run-new",
                task_id="bonds",
                trigger="scheduled",
                started_at=started_at + timedelta(hours=7),
                stale_before=started_at + timedelta(hours=7),
            )
        )

    def test_try_start_run_ignores_old_heartbeat(self) -> None:
        started_at = datetime(2026, 11, 27, 5, 0, 0)
        self.repo.start_run(
            run_id="run-stale-heartbeat",
            task_id="coupons",
            trigger="scheduled",
            started_at=started_at,
        )
        with self.repo._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE data_update_runs SET heartbeat_at = :heartbeat "
                    "WHERE run_id = :run_id"
                ),
                {
                    "heartbeat": "2026-11-27 04:00:00.000000",
                    "run_id": "run-stale-heartbeat",
                },
            )

        self.assertTrue(
            self.repo.try_start_run(
                run_id="run-new",
                task_id="bonds",
                trigger="scheduled",
                started_at=started_at,
                stale_before=started_at - timedelta(minutes=1),
            )
        )

    def test_update_run_log_keeps_status_running(self) -> None:
        started_at = datetime(2026, 11, 27, 5, 0, 0)
        self.repo.start_run(
            run_id="run-progress",
            task_id="coupons",
            trigger="scheduled",
            started_at=started_at,
        )

        updated = self.repo.update_run_log(
            run_id="run-progress",
            log_text="PROGRESS processed=100/300",
        )

        self.assertTrue(updated)
        row = self.repo.get_run("run-progress")
        assert row is not None
        self.assertEqual(row["status"], "running")
        self.assertIsNone(row["finished_at"])
        self.assertEqual(row["log_text"], "PROGRESS processed=100/300")
        heartbeat_at = row["heartbeat_at"]
        self.assertIsNotNone(heartbeat_at)

    def test_update_run_log_does_not_touch_finished_run(self) -> None:
        started_at = datetime(2026, 11, 27, 5, 0, 0)
        self.repo.start_run(
            run_id="run-finished",
            task_id="coupons",
            trigger="scheduled",
            started_at=started_at,
        )
        self.repo.finish_run(
            run_id="run-finished",
            status="success",
            finished_at=started_at + timedelta(seconds=30),
            log_text="FINAL",
        )

        updated = self.repo.update_run_log("run-finished", "LATE PROGRESS")

        self.assertFalse(updated)
        row = self.repo.get_run("run-finished")
        assert row is not None
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["log_text"], "FINAL")

    def test_prune_removes_old_finished_runs(self) -> None:
        old_started = datetime(2026, 1, 1, 10, 0, 0)
        self._run("old", "bonds", old_started)
        self._run("new", "bonds", datetime(2026, 11, 26, 10, 0, 0))

        deleted = self.repo.prune(retention_days=30, max_runs_per_task=200)

        self.assertGreaterEqual(deleted, 1)
        self.assertIsNotNone(self.repo.get_run("new"))
        self.assertIsNone(self.repo.get_run("old"))

    def test_prune_limits_runs_per_task(self) -> None:
        base = datetime(2026, 11, 26, 10, 0, 0)
        self._run("r1", "bonds", base)
        self._run("r2", "bonds", base + timedelta(minutes=1))
        self._run("r3", "bonds", base + timedelta(minutes=2))

        self.repo.prune(retention_days=90, max_runs_per_task=2)

        self.assertIsNone(self.repo.get_run("r1"))
        self.assertIsNotNone(self.repo.get_run("r2"))
        self.assertIsNotNone(self.repo.get_run("r3"))


if __name__ == "__main__":
    unittest.main()
