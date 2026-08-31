import uuid

from django.core.exceptions import ValidationError
from django.db import models


CALCULATION_VERSION = "1.5.0"


class SubjectType(models.TextChoices):
    EMPLOYEE = "employee", "Employee"
    ORG_UNIT = "org_unit", "Organisation unit"
    LOCATION = "location", "Location"
    LEGAL_ENTITY = "legal_entity", "Legal entity"
    OVERVIEW = "overview", "Overview"


class AttributionRole(models.TextChoices):
    RESPONSIBLE = "responsible", "Responsible"
    EXECUTOR = "executor", "Executor"
    REQUESTER = "requester", "Requester"
    REVIEWER = "reviewer", "Reviewer"


class PerformanceFact(models.Model):
    """Immutable, reproducible projection of a canonical operational event."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fact_key = models.CharField(max_length=240)
    calculation_version = models.CharField(max_length=32, default=CALCULATION_VERSION)
    source_domain = models.CharField(max_length=24)
    source_id = models.UUIDField()
    metric_code = models.CharField(max_length=80)
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="performance_facts")
    attribution_role = models.CharField(max_length=20, choices=AttributionRole.choices)
    occurred_at = models.DateTimeField(db_index=True)
    value = models.DecimalField(max_digits=20, decimal_places=4, default=1)
    sample_size = models.PositiveIntegerField(default=1)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True)
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True)
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("fact_key", "calculation_version"), name="performance_fact_version_key")]
        indexes = [
            models.Index(fields=("employee", "metric_code", "occurred_at"), name="perf_fact_emp_metric_time"),
            models.Index(fields=("source_domain", "source_id"), name="perf_fact_source"),
            models.Index(fields=("org_unit", "occurred_at"), name="perf_fact_org_time"),
        ]


class PerformanceAggregate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_type = models.CharField(max_length=24, choices=SubjectType.choices)
    subject_id = models.UUIDField(null=True, blank=True)
    period_from = models.DateTimeField()
    period_to = models.DateTimeField()
    reporting_timezone = models.CharField(max_length=64)
    metric_code = models.CharField(max_length=80)
    calculation_version = models.CharField(max_length=32, default=CALCULATION_VERSION)
    value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    sample_size = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=24, default="measured")
    explanation = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("subject_type", "subject_id", "period_from", "period_to", "reporting_timezone", "metric_code", "calculation_version"),
            name="performance_aggregate_slice",
        )]
        indexes = [models.Index(fields=("subject_type", "subject_id", "period_from", "period_to"), name="perf_aggregate_lookup")]


class PerformanceRecalculation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deduplication_key = models.CharField(max_length=240, unique=True)
    period_from = models.DateTimeField()
    period_to = models.DateTimeField()
    reporting_timezone = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("status", "created_at"), name="perf_recalc_claim")]


class PerformanceEventReceipt(models.Model):
    event_id = models.UUIDField(primary_key=True)
    recalculation = models.ForeignKey(PerformanceRecalculation, on_delete=models.PROTECT, related_name="event_receipts")
    created_at = models.DateTimeField(auto_now_add=True)


class ScoringPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ScoringPolicyVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(ScoringPolicy, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    weights = models.JSONField(default=dict)
    thresholds = models.JSONField(default=dict)
    minimum_samples = models.PositiveIntegerField(default=5)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("policy", "version"), name="performance_scoring_policy_version")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, published_at__isnull=False).exists():
            raise ValidationError("Published scoring policy versions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.published_at:
            raise ValidationError("Published scoring policy versions are immutable.")
        return super().delete(*args, **kwargs)
