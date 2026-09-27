import uuid
from django.conf import settings
from django.db import models


class CardCreation(models.Model):
    """Durable write receipt, not a second employee/customer directory.

    No names, card numbers, tracks, credentials or upstream bodies are stored.
    Uncertain attempts retain their reservation and are never replayed automatically.
    """
    id = models.UUIDField(primary_key=True, editable=False)
    connection_id = models.SlugField()
    organization_id = models.UUIDField()
    reservation_active = models.BooleanField(default=True)
    previous_customer_id = models.UUIDField(null=True, blank=True)
    card_digest = models.CharField(max_length=64)
    request_digest = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    customer_id = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=24, default="running")
    stage = models.CharField(max_length=40, default="preflight")
    completed_categories = models.JSONField(default=list)
    error_code = models.CharField(max_length=64, blank=True)
    error_diagnostics = models.JSONField(default=dict, blank=True)
    topup_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    topup_wallet_id = models.UUIDField(null=True, blank=True)
    topup_balance_before = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    topup_confirmed = models.BooleanField(default=False)
    error_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_correlation_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["connection_id", "organization_id", "card_digest"],
            condition=models.Q(status__in=["running", "succeeded", "needs_review"], reservation_active=True),
            name="iiko_card_creation_reservation",
        )]


class CardCategory(models.Model):
    """Scoped integration mapping; does not replace Organization/People directories."""
    connection_id = models.SlugField()
    organization_id = models.UUIDField()
    field = models.CharField(max_length=20, choices=[
        ("department", "Подразделение"), ("legalEntity", "Юридическое лицо"),
        ("cardType", "Тип карты"), ("approval", "Согласование"),
    ])
    name = models.CharField(max_length=150)
    external_id = models.UUIDField()
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(
            fields=["connection_id", "organization_id", "external_id"], name="iiko_category_scope_id",
        )]


class KnownGuest(models.Model):
    """Partial index of observed guests. Names are HMAC fingerprints, not stored profiles."""
    connection_id = models.SlugField()
    organization_id = models.UUIDField()
    customer_id = models.UUIDField()
    name_digest = models.CharField(max_length=64, db_index=True)
    observed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["connection_id", "organization_id", "customer_id"], name="iiko_known_guest_scope")]
