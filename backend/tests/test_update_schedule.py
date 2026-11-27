"""Тесты сбора расписания плановых обновлений данных."""

import unittest
from unittest.mock import patch

from app.services import update_schedule as schedule_module
from app.services.update_schedule import (
    DEPLOY_SYSTEMD_DIR,
    SCHEDULED_UPDATES,
    _read_timer_values,
    _state_for,
    collect_update_schedule,
    describe_schedule,
    parse_show_output,
    reset_cache,
    usec_to_iso,
)


class ScheduleRegistryTests(unittest.TestCase):
    def test_registry_covers_every_timer_file(self) -> None:
        timer_files = {
            path.name
            for path in DEPLOY_SYSTEMD_DIR.glob("bondsscreener-data-update-*.timer")
        }
        registry_units = {entry.timer_unit for entry in SCHEDULED_UPDATES}

        self.assertEqual(registry_units, timer_files)

    def test_timer_files_match_registry_units(self) -> None:
        for entry in SCHEDULED_UPDATES:
            with self.subTest(task_id=entry.task_id):
                path = DEPLOY_SYSTEMD_DIR / entry.timer_unit
                self.assertTrue(path.is_file())
                self.assertEqual(
                    _read_timer_values(path, "Unit"),
                    [entry.service_unit],
                )
                self.assertTrue(_read_timer_values(path, "OnCalendar"))


class DescribeScheduleTests(unittest.TestCase):
    def test_every_two_hours(self) -> None:
        self.assertEqual(describe_schedule("*-*-* 00/2:00:00"), "каждые 2 часа")

    def test_weekdays(self) -> None:
        self.assertEqual(
            describe_schedule("Tue,Fri 07:30:00 Europe/Moscow"),
            "вт, пт в 07:30",
        )

    def test_single_weekday(self) -> None:
        self.assertEqual(
            describe_schedule("Sat 11:30:00 Europe/Moscow"),
            "сб в 11:30",
        )

    def test_day_range(self) -> None:
        self.assertEqual(
            describe_schedule("*-*-20..30 18:00:00 Europe/Moscow"),
            "20–30 числа в 18:00",
        )

    def test_daily(self) -> None:
        self.assertEqual(
            describe_schedule("*-*-* 03:00:00 Europe/Moscow"),
            "ежедневно в 03:00",
        )

    def test_unknown_expression(self) -> None:
        self.assertIsNone(describe_schedule("Mon *-*-* 12:00:00 UTC"))
        self.assertIsNone(describe_schedule(None))
        self.assertIsNone(describe_schedule(""))


class ParseShowOutputTests(unittest.TestCase):
    def test_parses_properties(self) -> None:
        text = "LoadState=loaded\nActiveState=active\n\nBroken line\n"
        self.assertEqual(
            parse_show_output(text),
            {"LoadState": "loaded", "ActiveState": "active"},
        )


class UsecToIsoTests(unittest.TestCase):
    def test_converts_microseconds(self) -> None:
        self.assertEqual(usec_to_iso("1700000000000000"), "2023-11-14T22:13:20Z")

    def test_rejects_empty_and_invalid(self) -> None:
        self.assertIsNone(usec_to_iso(None))
        self.assertIsNone(usec_to_iso("0"))
        self.assertIsNone(usec_to_iso("n/a"))


class StateTests(unittest.TestCase):
    def test_active_enabled_timer_is_scheduled(self) -> None:
        self.assertEqual(
            _state_for(
                {
                    "LoadState": "loaded",
                    "ActiveState": "active",
                    "UnitFileState": "enabled",
                }
            ),
            ("scheduled", True, True),
        )

    def test_inactive_timer_is_paused(self) -> None:
        self.assertEqual(
            _state_for(
                {
                    "LoadState": "loaded",
                    "ActiveState": "inactive",
                    "UnitFileState": "enabled",
                }
            ),
            ("paused", True, False),
        )

    def test_disabled_timer(self) -> None:
        self.assertEqual(
            _state_for(
                {
                    "LoadState": "loaded",
                    "ActiveState": "inactive",
                    "UnitFileState": "disabled",
                }
            ),
            ("disabled", False, False),
        )

    def test_missing_unit(self) -> None:
        self.assertEqual(
            _state_for({"LoadState": "not-found"}),
            ("not_installed", False, False),
        )


class CollectScheduleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_cache()

    async def test_falls_back_to_files_without_systemd(self) -> None:
        with patch.object(schedule_module, "_find_systemctl", return_value=None):
            snapshot = await collect_update_schedule(use_cache=False)

        self.assertFalse(snapshot.systemd_available)
        self.assertEqual(len(snapshot.items), len(SCHEDULED_UPDATES))
        for item in snapshot.items:
            self.assertEqual(item["source"], "files")
            self.assertEqual(item["state"], "unknown")
            self.assertIsNone(item["next_elapse"])
            self.assertTrue(item["schedule"])

    async def test_uses_systemd_state_and_next_run(self) -> None:
        bonds_properties = {
            "LoadState": "loaded",
            "ActiveState": "active",
            "UnitFileState": "enabled",
            "NextElapseUSecRealtime": "1700000000000000",
            "LastTriggerUSec": "1699990000000000",
        }

        async def fake_show(_systemctl: str, unit: str):
            if unit == "bondsscreener-data-update-bonds.timer":
                return bonds_properties
            return None

        with patch.object(schedule_module, "_find_systemctl", return_value="systemctl"):
            with patch.object(schedule_module, "_show_unit", side_effect=fake_show):
                snapshot = await collect_update_schedule(use_cache=False)

        self.assertTrue(snapshot.systemd_available)
        bonds = next(item for item in snapshot.items if item["task_id"] == "bonds")
        self.assertEqual(bonds["state"], "scheduled")
        self.assertTrue(bonds["enabled"])
        self.assertTrue(bonds["active"])
        self.assertEqual(bonds["next_elapse"], "2023-11-14T22:13:20Z")
        self.assertEqual(bonds["last_trigger_at"], "2023-11-14T19:26:40Z")

        other = next(item for item in snapshot.items if item["task_id"] == "ipc")
        self.assertEqual(other["source"], "files")
        self.assertIsNone(other["next_elapse"])

    async def test_cache_is_reused(self) -> None:
        calls = 0

        async def fake_show(_systemctl: str, _unit: str):
            nonlocal calls
            calls += 1
            return None

        with patch.object(schedule_module, "_find_systemctl", return_value="systemctl"):
            with patch.object(schedule_module, "_show_unit", side_effect=fake_show):
                await collect_update_schedule()
                await collect_update_schedule()

        self.assertEqual(calls, len(SCHEDULED_UPDATES))

    async def test_missing_directory_keeps_schedule_empty(self) -> None:
        with patch.object(schedule_module, "_find_systemctl", return_value=None):
            with self.assertLogs("app.services.update_schedule", level="WARNING"):
                snapshot = await collect_update_schedule(
                    systemd_dir=DEPLOY_SYSTEMD_DIR / "missing",
                    use_cache=False,
                )

        for item in snapshot.items:
            self.assertIsNone(item["schedule"])
            self.assertIsNone(item["schedule_human"])


if __name__ == "__main__":
    unittest.main()
