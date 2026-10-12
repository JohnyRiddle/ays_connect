"""Shared atomic rate counters: enforce the same limit across API processes."""
import hashlib
import time
from datetime import datetime, timezone
from django.db import transaction
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle
from .models import RegistrationRateBucket


class RegistrationThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        scope = getattr(view, "throttle_scope", None)
        rate = api_settings.DEFAULT_THROTTLE_RATES.get(scope)
        if not rate:
            return True
        limit, duration = self.parse_rate(rate)
        now = time.time()
        window = int(now // duration)
        end = (window + 1) * duration
        key = hashlib.sha256(f"{scope}:{self.get_ident(request)}:{window}".encode()).hexdigest()
        self.remaining_wait = end - now
        with transaction.atomic():
            RegistrationRateBucket.objects.get_or_create(key=key, defaults={"expires_at": datetime.fromtimestamp(end, timezone.utc)})
            row = RegistrationRateBucket.objects.select_for_update().get(pk=key)
            if row.count >= limit:
                return False
            row.count += 1
            row.save(update_fields=["count"])
            expired = list(RegistrationRateBucket.objects.filter(expires_at__lte=datetime.fromtimestamp(now, timezone.utc)).values_list("pk", flat=True)[:100])
            RegistrationRateBucket.objects.filter(pk__in=expired).delete()
            return True

    def wait(self):
        return self.remaining_wait
