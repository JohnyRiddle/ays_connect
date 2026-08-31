from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.management import call_command
from django.db import connection, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from performance.models import PerformanceRecalculation


class RecalculationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    @skipUnlessDBFeature("has_select_for_update_skip_locked")
    def test_workers_claim_distinct_jobs_with_skip_locked(self):
        start = timezone.now() - timedelta(days=4); end = timezone.now() - timedelta(days=3)
        for index in range(2):
            offset = timedelta(days=index)
            PerformanceRecalculation.objects.create(deduplication_key=f"concurrency:{index}", period_from=start + offset, period_to=end + offset, reporting_timezone="UTC")

        def worker():
            connections.close_all()
            call_command("process_performance", batch_size=1, verbosity=0)
            connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(PerformanceRecalculation.objects.filter(status=PerformanceRecalculation.Status.COMPLETED).count(), 2)
