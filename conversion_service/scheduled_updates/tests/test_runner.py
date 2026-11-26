import unittest
from unittest.mock import Mock, patch

from conversion_service.scheduled_updates.runner import run_task, run_task_with_journal


class ScheduledUpdateRunnerTests(unittest.TestCase):
    def test_invokes_requested_task_and_returns_result(self):
        result = {"status": "ok", "updated": 3}
        runner = Mock(return_value=result)

        self.assertEqual(run_task("currency", runner), result)
        runner.assert_called_once_with("currency")

    def test_service_error_result_fails_task(self):
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            run_task("ruonia", Mock(return_value={"status": "error", "error": "write failed"}))

    def test_partial_trading_history_failure_fails_task(self):
        with self.assertRaisesRegex(RuntimeError, "partially failed"):
            run_task("trading_history", Mock(return_value={"updated": 4, "failed": 1, "errors": [{"secid": "X"}]}))

    def test_successful_trading_history_passes(self):
        result = {"updated": 5, "failed": 0, "total": 5, "errors": []}
        self.assertEqual(run_task("trading_history", Mock(return_value=result)), result)

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_records_success(self, repository_cls):
        repository = repository_cls.return_value
        result = {"status": "ok", "updated": 3}

        self.assertEqual(run_task_with_journal("currency", Mock(return_value=result)), result)

        repository.start_run.assert_called_once()
        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["task_id"], "currency")
        self.assertEqual(kwargs["trigger"], "scheduled")
        self.assertEqual(kwargs["status"], "success")
        self.assertIn("RESULT", kwargs["log_text"])

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_records_error_and_reraises(self, repository_cls):
        repository = repository_cls.return_value

        with self.assertRaisesRegex(RuntimeError, "write failed"):
            run_task_with_journal(
                "ruonia",
                Mock(return_value={"status": "error", "error": "write failed"}),
            )

        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["task_id"], "ruonia")
        self.assertEqual(kwargs["status"], "error")
        self.assertIn("write failed", kwargs["error_message"])
        self.assertIn("EXCEPTION", kwargs["log_text"])

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_uses_canonical_task_id(self, repository_cls):
        repository = repository_cls.return_value
        run_task_with_journal(
            "trading_history",
            Mock(return_value={"updated": 1, "failed": 0}),
        )

        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["task_id"], "trading-history")


if __name__ == "__main__":
    unittest.main()
