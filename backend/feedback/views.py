from django.db import transaction
from rest_framework import serializers, generics
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from audit.services import AuditService
from events.services import DomainEventService
from .models import Feedback
from .permissions import ActiveFeedbackUser, OwnerOnly, is_owner


class Submission(serializers.Serializer):
    command_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Feedback.Kind.choices)
    text = serializers.CharField(max_length=3000, trim_whitespace=True, allow_blank=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Допустимы только тип, текст и идентификатор отправки."]})
        return super().to_internal_value(data)


class FeedbackSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email

    class Meta:
        model = Feedback
        fields = ("id", "kind", "text", "author_name", "created_at", "delivery_status", "error_code", "delivered_at")


class Conflict(APIException):
    status_code = 409
    default_detail = "Эта отправка уже сохранена с другим текстом. Откройте новую форму."


class PrivateResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class SubmitView(PrivateResponseMixin, APIView):
    permission_classes = [ActiveFeedbackUser]
    throttle_scope = "feedback"

    @transaction.atomic
    def post(self, request):
        serializer = Submission(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        item, created = Feedback.objects.get_or_create(
            author=request.user, command_id=values["command_id"],
            defaults={"kind": values["kind"], "text": values["text"]},
        )
        if (item.kind, item.text) != (values["kind"], values["text"]):
            raise Conflict()
        if created:
            # Generic audit/outbox readers must never receive the private body.
            AuditService.record(action="feedback.submitted", entity=item, actor_user=request.user)
            DomainEventService.publish(event_type="feedback.submitted", entity=item,
                                       actor=request.user, payload={"feedback_id": str(item.pk)})
        return Response({"id": str(item.pk), "saved": True}, status=201 if created else 200)


class CapabilitiesView(PrivateResponseMixin, APIView):
    permission_classes = [ActiveFeedbackUser]

    def get(self, request):
        return Response({"can_read": is_owner(request.user)})


class OwnerList(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = [OwnerOnly]
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.select_related("author").all()


class OwnerDetail(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = [OwnerOnly]
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.select_related("author").all()


class RetryView(PrivateResponseMixin, APIView):
    permission_classes = [OwnerOnly]

    @transaction.atomic
    def post(self, request, pk):
        item = get_object_or_404(Feedback.objects.select_for_update(), pk=pk)
        if item.delivery_status not in {"failed", "unknown"}:
            raise Conflict("Повтор допустим только после проверки ошибки доставки.")
        if not isinstance(request.data, dict) or request.data.get("confirmed_not_received") is not True:
            raise serializers.ValidationError("Подтвердите, что сообщение не получено в Telegram. При неизвестном результате возможен дубль.")
        item.delivery_status = "pending"
        item.error_code = ""
        item.next_attempt_at = None
        item.lease_token = None
        item.save(update_fields=["delivery_status", "error_code", "next_attempt_at", "lease_token"])
        AuditService.record(action="feedback.delivery_retry_requested", entity=item, actor_user=request.user)
        return Response({"status": "pending"})
