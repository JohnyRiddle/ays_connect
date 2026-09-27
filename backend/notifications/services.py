from datetime import datetime,timedelta,timezone as dt_timezone
from string import Formatter
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from employees.models import Employee
from events.models import OutboxEvent
from .models import Notification,NotificationDelivery,NotificationDeliveryAttempt,NotificationIntent,NotificationPreference,NotificationQuietHours,NotificationTemplate,TelegramAccount
ALLOWED_EVENTS={"notification.requested"};MANDATORY_IN_APP={"SLA_ESCALATION"};MAX_ATTEMPTS=5
DEFAULT_TEMPLATE={"title":"SLA: заявка {request_id}","body":"Нарушение SLA, уровень {level}. Событие: {event_type}.","allowed":["request_id","level","event_type"]}
PEOPLE_TEMPLATES={
    "WORK_TASK_REOPENED":{"title":"Задача возвращена в работу","body":"{task_number}. Инициатор: {actor_name}. Причина: {reason_text}","allowed":["task_number","actor_name","reason_text"]},
    "WORK_TASK_REJECTED":{"title":"Результат задачи отклонён","body":"{task_number}. Инициатор: {actor_name}. Причина: {reason_text}","allowed":["task_number","actor_name","reason_text"]},
    "PEOPLE_INVITATION_EXPIRED":{"title":"Истёк срок приглашения","body":"Приглашение {invitation_id} больше не действует.","allowed":["invitation_id"]},
    "PEOPLE_STEP_OVERDUE":{"title":"Просрочен шаг адаптации","body":"Не завершён шаг: {step_title}.","allowed":["step_title"]},
    "PEOPLE_ONBOARDING_REOPEN_BLOCKED":{"title":"Возврат адаптации требует решения","body":"Завершённая адаптация {onboarding_id} не открыта: сначала явно отмените текущую адаптацию.","allowed":["onboarding_id"]},
    "PROJECT_TASK_REOPENED":{"title":"Проект открыт повторно","body":"Проект {project_number} открыт повторно после возврата задачи.","allowed":["project_number"]},
    "PROJECT_LIFECYCLE":{"title":"Изменён статус проекта","body":"Проект {project_number}: действие {lifecycle_action}.","allowed":["project_number","lifecycle_action"]},
    "PROJECT_MEMBER_ADDED":{"title":"Вы добавлены в проект","body":"Вы добавлены в проект {project_number}.","allowed":["project_number"]},
    "PROJECT_MANAGER_CHANGED":{"title":"Назначен руководитель проекта","body":"Вы назначены руководителем проекта {project_number}.","allowed":["project_number"]},
    "PROJECT_MILESTONE_ASSIGNED":{"title":"Назначена контрольная точка","body":"Проект {project_number}: контрольная точка {milestone_name}.","allowed":["project_number","milestone_name"]},
    "PROJECT_MILESTONE_DUE":{"title":"Наступил срок контрольной точки","body":"Проект {project_number}: срок контрольной точки {milestone_name} наступил.","allowed":["project_number","milestone_name"]},
    "PROJECT_COMMENT_MENTIONED":{"title":"Упоминание в проекте","body":"Вы упомянуты в обсуждении проекта {project_number}.","allowed":["project_number"]},
    "PEOPLE_CHANGE_APPROVED":{"title":"Изменение данных одобрено","body":"Запрос на изменение поля {field_type} одобрен.","allowed":["field_type"]},
    "PEOPLE_CHANGE_REJECTED":{"title":"Изменение данных отклонено","body":"Запрос на изменение поля {field_type} отклонён.","allowed":["field_type"]},
    "PEOPLE_CHANGE_APPLIED":{"title":"Данные профиля изменены","body":"Изменение поля {field_type} применено.","allowed":["field_type"]},
    "PEOPLE_CHANGE_FAILED":{"title":"Изменение данных не применено","body":"Не удалось применить изменение поля {field_type}.","allowed":["field_type"]},
}
def validate_template(text,allowed):
    for _,field,fmt,conversion in Formatter().parse(text):
        if field and (field not in allowed or any(x in field for x in ".[]") or fmt or conversion):raise ValidationError(f"Unsafe or unavailable template variable: {field}")
def render_template(text,payload,allowed):validate_template(text,allowed);return text.format_map({key:str(payload.get(key,"")) for key in allowed})
def preference_enabled(employee,reason,channel="in_app"):
    if channel=="in_app" and reason in MANDATORY_IN_APP:return True
    pref=NotificationPreference.objects.filter(employee=employee,channel=channel,reason=reason).first() or NotificationPreference.objects.filter(employee=employee,channel=channel,reason="*").first();return pref.enabled if pref else True
def quiet_hours_end(employee,now=None):
    quiet=NotificationQuietHours.objects.filter(employee=employee,enabled=True).first()
    if not quiet:return None
    now=now or timezone.now();zone=ZoneInfo(quiet.timezone);local=now.astimezone(zone);start,end=quiet.starts_at,quiet.ends_at;active=(start<=local.time()<end) if start<end else (local.time()>=start or local.time()<end)
    if not active:return None
    end_date=local.date() if local.time()<end else local.date()+timedelta(days=1);candidate=datetime.combine(end_date,end,tzinfo=zone);return candidate.astimezone(dt_timezone.utc)
class NotificationChannelRouter:
    @staticmethod
    def route(notification,reason):
        from django.conf import settings
        employee=notification.recipient_employee;channels=["in_app"]
        if reason in {"WORK_TASK_REOPENED","WORK_TASK_REJECTED","PEOPLE_INVITATION_EXPIRED","PEOPLE_STEP_OVERDUE","PEOPLE_ONBOARDING_REOPEN_BLOCKED","PROJECT_LIFECYCLE","PROJECT_MEMBER_ADDED","PROJECT_MANAGER_CHANGED","PROJECT_MILESTONE_ASSIGNED","PROJECT_MILESTONE_DUE","PROJECT_TASK_REOPENED","PROJECT_COMMENT_MENTIONED"}: channels.append("email")
        if notification.priority in {"warning","critical"}:channels.append("telegram")
        if notification.priority=="critical":channels.append("email")
        for channel in channels:
            snapshot={"reason":reason,"priority":notification.priority,"preference_enabled":preference_enabled(employee,reason,channel),"mandatory_in_app":channel=="in_app" and reason in MANDATORY_IN_APP}
            status="pending";code="";next_at=None
            enabled=channel=="in_app" or (channel=="telegram" and settings.NOTIFICATIONS_TELEGRAM_ENABLED) or (channel=="email" and settings.NOTIFICATIONS_EMAIL_ENABLED)
            if not enabled:status,code="suppressed","CHANNEL_DISABLED"
            elif not snapshot["preference_enabled"]:status,code="suppressed","PREFERENCE_DISABLED"
            elif channel=="telegram" and not TelegramAccount.objects.filter(employee=employee,is_active=True,delivery_disabled_at__isnull=True).exists():status,code="suppressed","RECIPIENT_NOT_LINKED"
            elif channel=="email" and not notification.recipient.email:status,code="suppressed","RECIPIENT_EMAIL_MISSING"
            elif channel!="in_app":
                bypass=channel=="telegram" and notification.priority=="critical" and reason in MANDATORY_IN_APP;next_at=None if bypass else quiet_hours_end(employee)
                snapshot.update({"quiet_hours_deferred":bool(next_at),"bypass_quiet_hours":bypass})
            NotificationDelivery.objects.get_or_create(notification=notification,channel=channel,defaults={"status":status,"last_error_code":code,"next_attempt_at":next_at,"routing_snapshot":snapshot})
@transaction.atomic
def ingest_event(event):
    if event.event_type not in ALLOWED_EVENTS:return None
    payload=event.payload or {};reason=payload.get("reason","");intent,created=NotificationIntent.objects.get_or_create(source_event_id=event.event_id,defaults={"event_type":event.event_type,"reason":reason,"payload":payload})
    if not created and intent.status==NotificationIntent.Status.MATERIALIZED:return intent
    try:
        employee=Employee.objects.select_related("user").get(pk=payload.get("recipient_employee_id"),is_active=True,user__isnull=False)
        if reason.startswith('PROJECT_'):
            from projects.policies import ProjectAccessPolicy
            if not ProjectAccessPolicy.visible_to(employee).filter(pk=payload.get('project_id')).exists():
                intent.status="materialized";intent.processed_at=timezone.now();intent.last_error="";intent.save(update_fields=["status","processed_at","last_error"])
                return intent
        if reason in {'WORK_TASK_REOPENED','WORK_TASK_REJECTED'}:
            from work_tasks.selectors import TaskSelector
            if not TaskSelector.visible_to(employee).filter(pk=payload.get('task_id')).exists():
                intent.status="materialized";intent.processed_at=timezone.now();intent.last_error="";intent.save(update_fields=["status","processed_at","last_error"])
                return intent
        template=NotificationTemplate.objects.filter(code=reason,is_active=True).first();fallback=PEOPLE_TEMPLATES.get(reason,DEFAULT_TEMPLATE);title_source=template.title_template if template else fallback["title"];body_source=template.body_template if template else fallback["body"];allowed=template.allowed_variables if template else fallback["allowed"]
        item,_=Notification.objects.get_or_create(intent=intent,recipient_employee=employee,defaults={"recipient":employee.user,"template":template,"notification_type":"sla_escalation" if reason=="SLA_ESCALATION" else "system","priority":"critical" if reason=="SLA_ESCALATION" else "info","title":render_template(title_source,payload,allowed),"message":render_template(body_source,payload,allowed),"entity_type":"ServiceRequest","entity_id":str(payload.get("request_id") or ""),"action_url":f"/#requests/{payload.get('request_id')}" if payload.get("request_id") else ""})
        if reason in {'WORK_TASK_REOPENED','WORK_TASK_REJECTED'}:
            item.entity_type='Task';item.entity_id=str(payload.get('task_id',''));item.action_url=f'/tasks/{item.entity_id}'
            item.save(update_fields=['entity_type','entity_id','action_url'])
        elif reason in {'PEOPLE_INVITATION_EXPIRED','PEOPLE_STEP_OVERDUE','PEOPLE_ONBOARDING_REOPEN_BLOCKED'}:
            item.entity_type='EmployeeInvitation' if reason=='PEOPLE_INVITATION_EXPIRED' else 'OnboardingInstance'
            item.entity_id=str(payload.get('invitation_id') or payload.get('onboarding_id') or '')
            item.action_url=''
            item.save(update_fields=['entity_type','entity_id','action_url'])
        elif reason in {'PROJECT_TASK_REOPENED','PROJECT_LIFECYCLE','PROJECT_MEMBER_ADDED','PROJECT_MANAGER_CHANGED','PROJECT_MILESTONE_ASSIGNED','PROJECT_MILESTONE_DUE','PROJECT_COMMENT_MENTIONED'}:
            item.entity_type='Project';item.entity_id=str(payload.get('project_id') or '')
            item.action_url=f'/projects/{item.entity_id}' if item.entity_id else ''
            item.save(update_fields=['entity_type','entity_id','action_url'])
        NotificationChannelRouter.route(item,reason)
        intent.status="materialized";intent.processed_at=timezone.now();intent.last_error="";intent.save(update_fields=["status","processed_at","last_error"]);return intent
    except Exception as exc:intent.status="failed";intent.last_error=str(exc)[:2000];intent.save(update_fields=["status","last_error"]);raise
def ingest_pending(batch_size=100,reconcile=False):
    statuses=["pending"]+(["processed"] if reconcile else []);events=list(OutboxEvent.objects.filter(event_type__in=ALLOWED_EVENTS,status__in=statuses).exclude(event_id__in=NotificationIntent.objects.filter(status='materialized').values('source_event_id')).order_by("created_at")[:batch_size]);done=0
    for event in events:
        try:
            ingest_event(event);done+=1
            if event.status=="pending":event.status="processed";event.processed_at=timezone.now();event.attempts+=1;event.last_error="";event.save(update_fields=["status","processed_at","attempts","last_error"])
        except Exception as exc:
            if event.status=="pending":event.status="failed";event.attempts+=1;event.last_error=str(exc)[:2000];event.save(update_fields=["status","attempts","last_error"])
    return done
def deliver_one(delivery,handler=None):
    from .channels import CHANNEL_HANDLERS,ProviderFailure
    if not Employee.objects.filter(pk=delivery.notification.recipient_employee_id,is_active=True,user__is_active=True).exclude(status='terminated').exists():
        delivery.status='suppressed';delivery.last_error_code='RECIPIENT_INACTIVE';delivery.processing_started_at=None
        delivery.save(update_fields=['status','last_error_code','processing_started_at','updated_at'])
        return
    if delivery.notification.entity_type == 'Project':
        from projects.policies import ProjectAccessPolicy
        if not ProjectAccessPolicy.visible_to(delivery.notification.recipient_employee).filter(pk=delivery.notification.entity_id).exists():
            delivery.status='suppressed';delivery.last_error_code='PROJECT_ACCESS_REVOKED';delivery.processing_started_at=None
            delivery.save(update_fields=['status','last_error_code','processing_started_at','updated_at'])
            return
    if delivery.notification.entity_type == 'Task':
        from work_tasks.selectors import TaskSelector
        if not TaskSelector.visible_to(delivery.notification.recipient_employee).filter(pk=delivery.notification.entity_id).exists():
            delivery.status='suppressed';delivery.last_error_code='TASK_ACCESS_REVOKED';delivery.processing_started_at=None
            delivery.save(update_fields=['status','last_error_code','processing_started_at','updated_at'])
            return
    now=timezone.now();delivery.attempts+=1;delivery.provider_started_at=now;delivery.save(update_fields=["attempts","provider_started_at","updated_at"])
    try:
        result=(handler or CHANNEL_HANDLERS[delivery.channel]()).send(delivery);delivery.status="delivered";delivery.delivered_at=timezone.now();delivery.last_error="";delivery.last_error_code="";delivery.provider_message_id=result.message_id;delivery.provider_metadata=result.metadata;delivery.notification.delivered_at=delivery.delivered_at if delivery.channel=="in_app" else delivery.notification.delivered_at;delivery.notification.save(update_fields=["delivered_at"]);NotificationDeliveryAttempt.objects.create(delivery=delivery,attempt_number=delivery.attempts,successful=True,outcome="delivered",provider_metadata=result.metadata)
    except ProviderFailure as exc:
        delivery.last_error=str(exc)[:2000];delivery.last_error_code=exc.code
        if exc.ambiguous:delivery.status="unknown";outcome="unknown"
        elif exc.retryable and delivery.attempts<MAX_ATTEMPTS:delivery.status="retry";delivery.next_attempt_at=timezone.now()+timedelta(seconds=exc.retry_after or min(3600,2**delivery.attempts*60));outcome="retry"
        else:delivery.status="failed";outcome="failed"
        NotificationDeliveryAttempt.objects.create(delivery=delivery,attempt_number=delivery.attempts,outcome=outcome,error=delivery.last_error,error_code=exc.code);raise
    finally:delivery.processing_started_at=None;delivery.save(update_fields=["attempts","status","delivered_at","processing_started_at","provider_started_at","last_error","last_error_code","next_attempt_at","provider_message_id","provider_metadata","updated_at"])
def reconcile_deliveries(now=None):
    now=now or timezone.now();stale=now-timedelta(minutes=5);count=0
    for item in NotificationDelivery.objects.filter(status="processing",processing_started_at__lt=stale):
        if item.provider_started_at:item.status="unknown";item.last_error_code="DELIVERY_OUTCOME_UNKNOWN"
        else:item.status="retry";item.next_attempt_at=now
        item.processing_started_at=None;item.save(update_fields=["status","last_error_code","next_attempt_at","processing_started_at","updated_at"]);count+=1
    NotificationDelivery.objects.filter(status="pending",next_attempt_at__lte=now).update(next_attempt_at=None);return count
def process_deliveries(batch_size=100):
    done=0
    while done<batch_size:
        with transaction.atomic():
            item=NotificationDelivery.objects.select_for_update(skip_locked=True).filter(status__in=["pending","retry"]).filter(Q(next_attempt_at__isnull=True)|Q(next_attempt_at__lte=timezone.now())).order_by("created_at").first()
            if not item:break
            item.status="processing";item.processing_started_at=timezone.now();item.provider_started_at=None;item.save(update_fields=["status","processing_started_at","provider_started_at","updated_at"]);pk=item.pk
        try:deliver_one(NotificationDelivery.objects.select_related("notification__recipient","notification__recipient_employee","notification__intent","notification__template").get(pk=pk))
        except Exception:pass
        done+=1
    return done
def validate_timezone(value):
    try:ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:raise ValidationError("Unknown IANA timezone") from exc
    return value
