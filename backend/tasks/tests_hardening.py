from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class ScheduleWorkerHardeningTests(TestCase):
    @patch("tasks.management.commands.run_schedules.record_worker_cycle")
    @patch("tasks.management.commands.run_schedules.process_learning_deadlines")
    @patch("tasks.management.commands.run_schedules.run_due_schedules")
    def test_learning_counters_are_aggregated_for_heartbeat(self, run_due, learning, heartbeat):
        run_due.return_value = {"tasks": 2, "checklists": 3, "skipped": 1}
        learning.return_value = {"courses_overdue": 4, "due_reminders": 5}

        call_command("run_schedules")

        heartbeat.assert_called_once_with(
            "schedule",
            processed=14,
            metadata={"skipped": 1, "learning": learning.return_value},
        )
