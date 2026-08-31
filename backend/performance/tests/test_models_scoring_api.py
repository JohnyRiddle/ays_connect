from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from employees.models import Employee
from performance.models import ScoringPolicy, ScoringPolicyVersion
from performance.scoring import calculate_score


class ScoringTests(TestCase):
    def setUp(self):
        policy = ScoringPolicy.objects.create(code="standard", name="Standard")
        self.policy = ScoringPolicyVersion.objects.create(policy=policy, version=1, weights={"a": .6, "b": .4}, thresholds={"a": 100, "b": 50}, minimum_samples=5)

    def test_score_is_explainable_and_bounded(self):
        score, status, details = calculate_score({"a": SimpleNamespace(value=Decimal("120"), sample_size=5), "b": SimpleNamespace(value=Decimal("25"), sample_size=5)}, self.policy)
        self.assertEqual((score, status), (80.0, "measured")); self.assertEqual(len(details), 2)

    def test_sparse_data_is_neutral_not_zero(self):
        score, status, details = calculate_score({"a": SimpleNamespace(value=Decimal("100"), sample_size=1)}, self.policy)
        self.assertIsNone(score); self.assertEqual(status, "insufficient_data")

    def test_published_version_is_immutable(self):
        self.policy.published_at = timezone.now(); self.policy.save(); self.policy.weights = {"a": 1}
        with self.assertRaises(ValidationError): self.policy.save()


class PerformanceApiSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="worker", email="worker@example.test", password="secret")
        self.employee = Employee.objects.create(user=self.user, first_name="Ivan", last_name="Worker", employee_number="P-1")
        other_user = User.objects.create_user(username="other", email="other@example.test", password="secret")
        self.other = Employee.objects.create(user=other_user, first_name="Other", last_name="Person", employee_number="P-2")
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_me_is_available_and_has_period_semantics(self):
        response = self.client.get("/api/internal/v1/performance/me/", secure=True)
        self.assertEqual(response.status_code, 200, response.data); self.assertEqual(response.data["period"]["semantics"], "[from,to)")

    def test_foreign_employee_is_hidden_against_idor(self):
        response = self.client.get(f"/api/internal/v1/performance/employees/{self.other.pk}/summary/", secure=True)
        self.assertEqual(response.status_code, 404)

    def test_metric_registry_endpoint(self):
        response = self.client.get("/api/internal/v1/performance/metrics/task_deadline_compliance/", secure=True)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.data["category"], "SLA")

    def test_invalid_period_is_rejected(self):
        response = self.client.get("/api/internal/v1/performance/me/?from=2026-08-02&to=2026-08-01", secure=True)
        self.assertEqual(response.status_code, 400)
