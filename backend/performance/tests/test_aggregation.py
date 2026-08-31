from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from performance.engine import _metric_value, _percentile


def facts(*values): return [SimpleNamespace(value=Decimal(str(value))) for value in values]


class AggregationSemanticsTests(SimpleTestCase):
    def test_count_sums_values(self): self.assertEqual(_metric_value("tasks_completed", facts(1, 1, 1)), 3)
    def test_average(self): self.assertEqual(_metric_value("task_cycle_seconds_avg", facts(10, 20, 30)), 20)
    def test_median_odd(self): self.assertEqual(_metric_value("task_cycle_seconds_p50", facts(30, 10, 20)), 20)
    def test_median_even(self): self.assertEqual(_metric_value("task_cycle_seconds_p50", facts(10, 20)), 15)
    def test_p90_interpolates(self): self.assertEqual(_metric_value("task_cycle_seconds_p90", facts(10, 20)), Decimal("19.0"))
    def test_compliance_is_percentage(self): self.assertEqual(_metric_value("task_deadline_compliance", facts(1, 1, 0, 0)), 50)
    def test_rate_is_percentage(self): self.assertEqual(_metric_value("task_reopen_rate", facts(1, 0, 0, 0)), 25)
    def test_empty_population_is_none(self): self.assertIsNone(_metric_value("tasks_completed", []))
    def test_percentile_is_order_independent(self): self.assertEqual(_percentile([Decimal(100), Decimal(0), Decimal(50)], .5), 50)
