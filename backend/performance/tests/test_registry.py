from django.test import SimpleTestCase

from performance.registry import METRICS, metric_payload


class MetricRegistryTests(SimpleTestCase):
    def test_registry_has_exactly_thirty_stable_metrics(self):
        self.assertEqual(len(METRICS), 30)

    def test_categories_are_explicit(self):
        self.assertEqual({item.category for item in METRICS.values()}, {"VOLUME", "SPEED", "SLA", "QUALITY", "DISCIPLINE", "LOAD", "FLOW"})


def _metric_case(code):
    def test(self):
        payload = metric_payload(code)
        self.assertEqual(payload["code"], code)
        self.assertIn(payload["population"], {"activity", "cohort", "snapshot"})
        self.assertIn(payload["direction"], {"higher", "lower", "neutral"})
        self.assertTrue(payload["title"])
    return test


for _code in METRICS:
    setattr(MetricRegistryTests, f"test_definition_{_code}", _metric_case(_code))
