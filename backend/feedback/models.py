import uuid
from django.conf import settings
from django.db import models


class Feedback(models.Model):
    class Kind(models.TextChoices):
        IMPROVEMENT = "improvement", "Предложить улучшение"
        BUG = "bug", "Сообщить об ошибке"

    class Delivery(models.TextChoices):
        PENDING = "pending", "Ожидает доставки"
        SENDING = "sending", "Отправляется"
        DELIVERED = "delivered", "Доставлено"
        UNKNOWN = "unknown", "Результат неизвестен — нужна проверка"
        FAILED = "failed", "Нужна проверка настройки Telegram"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    command_id = models.UUIDField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_status = models.CharField(max_length=16, choices=Delivery.choices, default=Delivery.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True, editable=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=80, blank=True)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["author", "command_id"], name="feedback_author_command_unique")]

    def __str__(self):
        # Never leak the body into generic admin/audit object labels.
        return str(self.pk)
