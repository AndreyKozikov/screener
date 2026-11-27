import unittest
from unittest.mock import AsyncMock, Mock, patch

from conversion_service.scheduled_updates.runner import _run, run_task, run_task_with_journal


class ScheduledUpdateRunnerTests(unittest.TestCase):
    def test_invokes_requested_task_and_returns_result(self):
        result = {"status": "ok", "updated": 3}
        runner = Mock(return_value=result)

        self.assertEqual(run_task("currency", runner), result)
        runner.assert_called_once_with("currency")

    def test_service_error_result_fails_task(self):
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            run_task("ruonia", Mock(return_value={"status": "error", "error": "write failed"}))

    def test_partial_trading_history_passes(self):
        result = {
            "updated": 4,
            "failed": 1,
            "total": 5,
            "errors": [{"secid": "X", "error": "boom"}],
        }
        self.assertEqual(run_task("trading_history", Mock(return_value=result)), result)

    def test_total_trading_history_failure_raises(self):
        with self.assertRaisesRegex(RuntimeError, "Не обновлены"):
            run_task(
                "trading_history",
                Mock(return_value={"updated": 0, "failed": 5, "total": 5, "errors": []}),
            )

    def test_successful_trading_history_passes(self):
        result = {"updated": 5, "failed": 0, "total": 5, "errors": []}
        self.assertEqual(run_task("trading_history", Mock(return_value=result)), result)

    @patch("conversion_service.app.services.coupon_service.get_coupon_service")
    def test_run_dispatches_coupons_refresh(self, get_service):
        result = {"status": "ok", "updated": 1}
        get_service.return_value.refresh_all = AsyncMock(return_value=result)

        self.assertEqual(_run("coupons"), result)
        get_service.return_value.refresh_all.assert_awaited_once_with(progress=None)

    @patch("conversion_service.app.services.bond_ratings_update_service.BondRatingsPipelineService")
    def test_run_dispatches_ratings_pipeline(self, pipeline_cls):
        result = {"total_bonds": 1, "updated": 1, "errors": 0, "skipped": 0}
        pipeline_cls.return_value.run_pipeline.return_value = result

        self.assertEqual(_run("ratings"), result)
        pipeline_cls.return_value.run_pipeline.assert_called_once_with()

    @patch("conversion_service.app.services.emitents_service.get_emitent_service")
    def test_run_dispatches_emitents_update(self, get_service):
        result = {"emitents": {"updated": 1}}
        get_service.return_value.update_emitents_data = AsyncMock(return_value=result)

        self.assertEqual(_run("emitents"), result)
        get_service.return_value.update_emitents_data.assert_awaited_once_with(None)

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_records_success(self, repository_cls):
        repository = repository_cls.return_value
        result = {"status": "ok", "updated": 3}

        self.assertEqual(run_task_with_journal("currency", Mock(return_value=result)), result)

        repository.try_start_run.assert_called_once()
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
    def test_journal_records_warning_for_partial_history(self, repository_cls):
        repository = repository_cls.return_value
        result = {
            "updated": 4,
            "failed": 1,
            "total": 5,
            "errors": [{"secid": "X", "error": "boom"}],
        }

        self.assertEqual(run_task_with_journal("trading_history", Mock(return_value=result)), result)

        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["status"], "success")
        self.assertIn("1 из 5", kwargs["warning_message"])
        self.assertIn("WARNING", kwargs["log_text"])
        self.assertIn("FINISH success", kwargs["log_text"])

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_uses_canonical_task_id(self, repository_cls):
        repository = repository_cls.return_value
        run_task_with_journal(
            "trading_history",
            Mock(return_value={"updated": 1, "failed": 0}),
        )

        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["task_id"], "trading-history")

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_waits_while_another_update_is_running(self, repository_cls):
        repository = repository_cls.return_value
        repository.try_start_run.side_effect = [False, False, True]
        sleep_func = Mock()
        runner = Mock(return_value={"status": "ok", "updated": 1})

        result = run_task_with_journal(
            "currency",
            runner,
            sleep_func=sleep_func,
            wait_interval=900,
            heartbeat_interval=None,
        )

        self.assertEqual(result, {"status": "ok", "updated": 1})
        self.assertEqual(sleep_func.call_count, 2)
        sleep_func.assert_called_with(900)
        self.assertEqual(repository.try_start_run.call_count, 3)
        runner.assert_called_once_with("currency")
        self.assertEqual(repository.finish_run.call_args.kwargs["status"], "success")

    def test_partial_coupons_is_success(self):
        result = {
            "status": "ok",
            "total_bonds": 10,
            "updated": 9,
            "errors": 1,
            "failed": 1,
            "error_samples": [{"secid": "X", "error": "boom"}],
        }
        self.assertEqual(run_task("coupons", Mock(return_value=result)), result)

    def test_total_coupons_failure_raises(self):
        with self.assertRaisesRegex(RuntimeError, "Не обновлены"):
            run_task(
                "coupons",
                Mock(
                    return_value={
                        "status": "ok",
                        "total_bonds": 5,
                        "updated": 0,
                        "errors": 5,
                        "failed": 5,
                    }
                ),
            )

    @patch("conversion_service.scheduled_updates.runner.DataUpdateRunsRepository")
    def test_journal_records_warning_for_partial_coupons(self, repository_cls):
        repository = repository_cls.return_value
        result = {
            "status": "ok",
            "total_bonds": 10,
            "updated": 9,
            "errors": 1,
            "failed": 1,
            "error_samples": [{"secid": "X", "error": "boom"}],
        }

        self.assertEqual(run_task_with_journal("coupons", Mock(return_value=result)), result)

        kwargs = repository.finish_run.call_args.kwargs
        self.assertEqual(kwargs["status"], "success")
        self.assertIn("1 из 10", kwargs["warning_message"])
        self.assertIn("X: boom", kwargs["warning_message"])


if __name__ == "__main__":
    unittest.main()
