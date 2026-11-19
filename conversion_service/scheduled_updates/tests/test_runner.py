import unittest
from unittest.mock import Mock

from conversion_service.scheduled_updates.runner import run_task


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


if __name__ == "__main__":
    unittest.main()
