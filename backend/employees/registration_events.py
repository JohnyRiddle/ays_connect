"""Consumer receipts for state projections committed by onboarding services.

These events have no email side effect: mail jobs have their own consumer and
provider evidence. A receipt must never be reported as notification delivery.
"""
from django.apps import apps
from django.db import transaction
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from django.utils import timezone
from events.models import OutboxEvent

REGISTRY = {
    "assignment_target.created": ("employees", "AssignmentTarget"),
    **{code: ("employees", "RegistrationRequest") for code in (
        "registration.submitted", "registration.email_confirmed", "registration.approved",
        "registration.rejected", "registration.cancelled", "registration.expired")},
    **{code: ("employees", "EmployeeObjectResponsibility") for code in (
        "people.responsibility.changed", "people.responsibility.ended")},
    **{code: ("employees", "Employee") for code in (
        "people.user.linked", "people.access_scope.changed", "people.employment_location.changed")},
    **{code: ("employees", "EmployeeInvitation") for code in (
        "people.invitation.created", "people.invitation.accepted")},
    "role.assigned": ("access_control", "EmployeeRole"),
    "role.revoked": ("access_control", "EmployeeRole"),
}


def process_state_events(limit=100):
    predicate = Q(pk__in=[])
    for label in set(REGISTRY.values()):
        model = apps.get_model(*label)
        entities = model.objects.all()
        if model.__name__ in {"EmployeeInvitation", "RegistrationRequest"}:
            entities = entities.filter(employment_location__isnull=False)
        ids = entities.annotate(consumer_id=Cast("pk", CharField())).values("consumer_id")
        predicate |= Q(event_type__in=[code for code, target in REGISTRY.items() if target == label], entity_type=model.__name__, entity_id__in=ids)
    ids = list(OutboxEvent.objects.filter(predicate, status="pending").order_by("created_at").values_list("pk", flat=True)[:limit])
    handled = 0
    for pk in ids:
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update(skip_locked=True).filter(pk=pk, status="pending").first()
            if not event:
                continue
            model = apps.get_model(*REGISTRY[event.event_type])
            if event.entity_type != model.__name__:
                continue
            qs = model.objects.filter(pk=event.entity_id)
            if model.__name__ in {"EmployeeInvitation", "RegistrationRequest"}:
                # Do not take over legacy onboarding events during this extension.
                qs = qs.filter(employment_location__isnull=False)
            if not qs.exists():
                continue
            event.status = "processed"
            event.processed_at = timezone.now()
            event.payload = {**event.payload, "consumer_receipt": "transactional_state_projection"}
            event.save(update_fields=["status", "processed_at", "payload"])
            handled += 1
    return handled
