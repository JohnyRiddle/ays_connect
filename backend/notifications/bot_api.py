"""A dedicated service identity can only redeem bindings and deliver task notices.

No bot token is accepted by the normal employee APIs. Raw credentials are never
stored here; operators provision hashes and rotate them outside the repository.
"""
import hashlib
import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from .linking import TelegramLinkService
from .models import NotificationDelivery, NotificationDeliveryAttempt, TelegramAccount


class BotIdentity:
    is_authenticated = True
    is_active = True
    is_superuser = False
    pk = 'corporate-telegram-bot'


class BotAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw = request.headers.get('Authorization', '')
        if not raw.startswith('Bearer ') or not settings.TELEGRAM_BOT_SERVICE_ENABLED:
            raise AuthenticationFailed('Bot credential required')
        digest = hashlib.sha256(raw[7:].encode()).hexdigest()
        hashes = (settings.TELEGRAM_BOT_SERVICE_TOKEN_SHA256, settings.TELEGRAM_BOT_SERVICE_PREVIOUS_TOKEN_SHA256)
        if not any(value and secrets.compare_digest(digest, value) for value in hashes):
            raise AuthenticationFailed('Invalid bot credential')
        return BotIdentity(), None

    def authenticate_header(self, request):
        return 'Bearer'


class RedeemSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    telegram_user_id = serializers.IntegerField(min_value=1)
    private_chat_id = serializers.IntegerField(min_value=1)
    username = serializers.CharField(max_length=80, required=False, allow_blank=True)


class ClaimSerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=25)


class LeaseSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()


class AckSerializer(LeaseSerializer):
    telegram_message_id = serializers.CharField(max_length=160)


class FailSerializer(LeaseSerializer):
    category = serializers.ChoiceField(choices=['retryable', 'blocked', 'permanent', 'ambiguous'])
    retry_after_seconds = serializers.IntegerField(min_value=1, max_value=86400, required=False)


class BindingResultSerializer(serializers.Serializer):
    linked = serializers.BooleanField()
    employee_id = serializers.UUIDField()


class PacketSerializer(serializers.Serializer):
    notification_id = serializers.IntegerField()
    delivery_id = serializers.IntegerField()
    event_id = serializers.UUIDField()
    event_type = serializers.CharField()
    event_version = serializers.IntegerField()
    recipient_employee_id = serializers.UUIDField()
    telegram_chat_id = serializers.IntegerField()
    task_id = serializers.UUIDField()
    task_number = serializers.CharField()
    task_title = serializers.CharField()
    location = serializers.DictField(allow_null=True)
    change = serializers.CharField()
    priority = serializers.CharField(allow_null=True)
    deadline = serializers.DateTimeField(allow_null=True)
    actor = serializers.DictField(allow_null=True)
    url = serializers.URLField()
    occurred_at = serializers.DateTimeField()
    lease_token = serializers.UUIDField()
    lease_expires_at = serializers.DateTimeField()


class ClaimResultSerializer(serializers.Serializer):
    results = PacketSerializer(many=True)


class BeginResultSerializer(serializers.Serializer):
    send_allowed = serializers.BooleanField()
    code = serializers.CharField(required=False)


class DeliveryResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['delivered', 'unknown', 'retry', 'failed'])


def allowed_delivery(delivery):
    from employees.assignment_targets import assignable_employees
    from work_tasks.models import Task
    from work_tasks.selectors import TaskSelector
    from access_control.services import PermissionService
    employee = delivery.notification.recipient_employee
    if not employee or not assignable_employees().filter(pk=employee.pk, user__is_active=True).exists():
        return 'RECIPIENT_INACTIVE'
    task = TaskSelector.visible_to(employee).filter(pk=delivery.notification.entity_id).first()
    if not task:
        return 'TASK_ACCESS_REVOKED'
    payload = delivery.notification.intent.payload
    internal = payload.get('is_internal')
    if payload.get('comment_id'):
        from work_tasks.models import TaskComment
        comment = TaskComment.objects.filter(pk=payload['comment_id'], task=task, deleted_at__isnull=True).first()
        if not comment:
            return 'COMMENT_UNAVAILABLE'
        internal = comment.is_internal
    if internal and not PermissionService.has_permission(employee=employee, permission='task.comment_internal', obj=task):
        return 'INTERNAL_ACCESS_REVOKED'
    from work_tasks.routing import eligible_for_location
    if not eligible_for_location(employee, task.location):
        return 'OBJECT_ACCESS_REVOKED'
    return ''


@transaction.atomic
def reconcile_leases():
    now = timezone.now()
    for item in NotificationDelivery.objects.select_for_update().filter(channel='telegram', status='processing', lease_token__isnull=False, lease_expires_at__lte=now):
        item.status = 'unknown' if item.provider_started_at else 'retry'
        item.last_error_code = 'DELIVERY_OUTCOME_UNKNOWN' if item.provider_started_at else 'LEASE_EXPIRED'
        item.processing_started_at = None
        item.next_attempt_at = now
        item.save()
        if item.provider_started_at:
            NotificationDeliveryAttempt.objects.get_or_create(delivery=item, attempt_number=item.attempts, defaults={'outcome': 'unknown', 'error_code': 'DELIVERY_OUTCOME_UNKNOWN'})


def packet(item, account):
    from work_tasks.models import Task
    from work_tasks.routing import project_for
    task = Task.objects.select_related('location').get(pk=item.notification.entity_id)
    intent = item.notification.intent
    payload = intent.payload
    actor = payload.get('actor')
    if actor:
        from employees.assignment_targets import assignment_visibility
        if not assignment_visibility(account.employee.user)[0].filter(pk=actor['id']).exists():
            actor = None
    return {'notification_id': item.notification_id, 'delivery_id': item.pk, 'event_id': str(intent.source_event_id), 'event_type': payload['source_event_type'], 'event_version': 1,
            'recipient_employee_id': str(account.employee_id), 'telegram_chat_id': account.telegram_chat_id,
            'task_id': str(task.pk), 'task_number': task.number, 'task_title': task.title,
            'location': {'id': str(task.location_id), 'name': task.location.name} if task.location else None,
            'change': item.notification.message, 'priority': None if project_for(task) else task.priority,
            'deadline': task.effective_due_at, 'actor': actor, 'url': settings.WORK_TASK_PUBLIC_BASE_URL.rstrip('/') + '/tasks/' + str(task.pk),
            'occurred_at': payload['occurred_at'], 'lease_token': str(item.lease_token), 'lease_expires_at': item.lease_expires_at}


class BotView(APIView):
    authentication_classes = [BotAuthentication]
    throttle_scope = 'telegram_bot'


class RedeemView(BotView):
    @extend_schema(request=RedeemSerializer, responses={200: BindingResultSerializer})
    def post(self, request):
        data = RedeemSerializer(data=request.data); data.is_valid(raise_exception=True)
        values = data.validated_data
        account = TelegramLinkService.consume(values['code'], values['telegram_user_id'], values['private_chat_id'], {'username': values.get('username', '')})
        return Response({'linked': True, 'employee_id': str(account.employee_id)})


class ClaimView(BotView):
    @extend_schema(request=ClaimSerializer, responses={200: ClaimResultSerializer})
    @transaction.atomic
    def post(self, request):
        data = ClaimSerializer(data=request.data); data.is_valid(raise_exception=True)
        if settings.TELEGRAM_DELIVERY_TRANSPORT != 'pull':
            raise ValidationError({'code': 'telegram_pull_disabled'})
        if not settings.NOTIFICATIONS_TELEGRAM_ENABLED:
            return Response({'results': []})
        reconcile_leases()
        now = timezone.now(); results = []
        qs = NotificationDelivery.objects.select_for_update(skip_locked=True).filter(channel='telegram', status__in=['pending', 'retry'], notification__intent__reason='WORK_TASK_EVENT').filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)).order_by('pk')
        for item in qs[:data.validated_data['limit']]:
            code = allowed_delivery(item)
            account = TelegramAccount.objects.filter(employee=item.notification.recipient_employee, is_active=True).first()
            from .services import preference_enabled
            if not preference_enabled(item.notification.recipient_employee, 'WORK_TASK_EVENT', 'telegram'):
                code = 'PREFERENCE_DISABLED'
            if code or not account or account.delivery_disabled_at:
                item.status = 'suppressed'; item.last_error_code = code or ('RECIPIENT_BLOCKED' if account else 'RECIPIENT_NOT_LINKED'); item.save(); continue
            item.lease_token = uuid.uuid4(); item.lease_expires_at = now + timedelta(seconds=settings.TELEGRAM_BOT_LEASE_SECONDS)
            item.status = 'processing'; item.processing_started_at = now; item.provider_started_at = None
            item.provider_metadata = {'account_id': str(account.pk)}; item.save()
            results.append(packet(item, account))
        return Response({'results': results})


def locked_lease(pk, data):
    item = NotificationDelivery.objects.select_for_update().filter(pk=pk, channel='telegram', notification__intent__reason='WORK_TASK_EVENT').first()
    if not item or item.lease_token != data['lease_token']:
        raise ValidationError({'code': 'lease_invalid'})
    return item


class BeginView(BotView):
    @extend_schema(request=LeaseSerializer, responses={200: BeginResultSerializer})
    @transaction.atomic
    def post(self, request, pk):
        data = LeaseSerializer(data=request.data); data.is_valid(raise_exception=True)
        item = locked_lease(pk, data.validated_data)
        if item.status != 'processing' or item.lease_expires_at <= timezone.now():
            raise ValidationError({'code': 'lease_expired'})
        code = allowed_delivery(item)
        from .services import preference_enabled
        if not settings.NOTIFICATIONS_TELEGRAM_ENABLED or not preference_enabled(item.notification.recipient_employee, 'WORK_TASK_EVENT', 'telegram'):
            code = 'CHANNEL_DISABLED'
        account = TelegramAccount.objects.filter(pk=item.provider_metadata.get('account_id'), is_active=True, delivery_disabled_at__isnull=True).first()
        if code or not account:
            item.status = 'suppressed'; item.last_error_code = code or 'BINDING_REVOKED'; item.save()
            return Response({'send_allowed': False})
        if item.provider_started_at:
            # Lost begin response must never authorize a second send.
            return Response({'send_allowed': False, 'code': 'send_already_started'})
        item.provider_started_at = timezone.now(); item.attempts += 1; item.save()
        return Response({'send_allowed': True})


class AckView(BotView):
    @extend_schema(request=AckSerializer, responses={200: DeliveryResultSerializer})
    @transaction.atomic
    def post(self, request, pk):
        data = AckSerializer(data=request.data); data.is_valid(raise_exception=True)
        item = locked_lease(pk, data.validated_data)
        message_id = data.validated_data['telegram_message_id']
        if item.status == 'delivered':
            if item.provider_message_id != message_id:
                raise ValidationError({'code': 'ack_conflict'})
            return Response({'status': 'delivered'})
        if item.status not in ['processing', 'unknown'] or not item.provider_started_at:
            raise ValidationError({'code': 'send_not_started'})
        item.status = 'delivered'; item.delivered_at = timezone.now(); item.provider_message_id = message_id; item.processing_started_at = None; item.last_error_code = ''; item.save()
        NotificationDeliveryAttempt.objects.update_or_create(delivery=item, attempt_number=item.attempts, defaults={'successful': True, 'outcome': 'delivered'})
        TelegramAccount.objects.filter(pk=item.provider_metadata.get('account_id')).update(last_success_at=item.delivered_at)
        return Response({'status': item.status})


class FailView(BotView):
    @extend_schema(request=FailSerializer, responses={200: DeliveryResultSerializer})
    @transaction.atomic
    def post(self, request, pk):
        data = FailSerializer(data=request.data); data.is_valid(raise_exception=True)
        item = locked_lease(pk, data.validated_data); category = data.validated_data['category']
        if item.status in ['unknown', 'failed', 'retry'] and item.last_error_code == category:
            return Response({'status': item.status})
        if item.status != 'processing' or not item.provider_started_at:
            raise ValidationError({'code': 'send_not_started'})
        item.status = 'unknown' if category == 'ambiguous' else ('retry' if category == 'retryable' and item.attempts < 5 else 'failed')
        item.last_error_code = category; item.processing_started_at = None
        item.next_attempt_at = timezone.now() + timedelta(seconds=max(data.validated_data.get('retry_after_seconds', 0), min(3600, 60 * 2 ** item.attempts))) if item.status == 'retry' else None
        item.save()
        NotificationDeliveryAttempt.objects.get_or_create(delivery=item, attempt_number=item.attempts, defaults={'outcome': item.status, 'error_code': category})
        if category == 'blocked':
            TelegramAccount.objects.filter(pk=item.provider_metadata.get('account_id')).update(delivery_disabled_at=timezone.now(), last_failure_at=timezone.now(), last_failure_code='blocked')
        return Response({'status': item.status})
