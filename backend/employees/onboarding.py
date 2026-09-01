import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .models import Employee, EmployeeInvitation, RegistrationRequest


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _event(action, entity, actor=None, old=None, new=None):
    AuditService.record(action=action, entity=entity, actor_user=actor, old_value=old, new_value=new)
    DomainEventService.publish(event_type=action, entity=entity, actor=actor, payload=new or {})


class InvitationService:
    @staticmethod
    @transaction.atomic
    def issue(*, employee, actor_user, delivery_address=""):
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        if not employee.is_active or employee.status in {"archived", "suspended", "dismissed", "terminated"}:
            raise ValidationError("Inactive employee cannot be invited.")
        if employee.user_id and employee.user.is_active:
            raise ValidationError("Employee already has an active account.")
        now = timezone.now()
        EmployeeInvitation.objects.filter(employee=employee, used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
        raw = secrets.token_urlsafe(32)
        invitation = EmployeeInvitation.objects.create(
            employee=employee, token_hash=token_hash(raw), delivery_address=delivery_address.lower().strip(),
            created_by=actor_user, expires_at=now + timedelta(hours=settings.EMPLOYEE_INVITATION_TTL_HOURS),
        )
        _event("employee.invitation.created", invitation, actor_user, new={"employee_id": str(employee.pk), "expires_at": invitation.expires_at})
        return invitation, raw

    @staticmethod
    @transaction.atomic
    def revoke(*, invitation, actor_user):
        invitation = EmployeeInvitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.used_at or invitation.revoked_at:
            raise ValidationError("Invitation is no longer active.")
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at"])
        _event("employee.invitation.revoked", invitation, actor_user, new={"employee_id": str(invitation.employee_id)})
        return invitation

    @staticmethod
    def context(token):
        invitation = EmployeeInvitation.objects.select_related("employee__position_ref", "employee__legal_entity").filter(token_hash=token_hash(token)).first()
        if not invitation or invitation.used_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
            return None
        return invitation

    @staticmethod
    @transaction.atomic
    def activate(*, token, password, password_confirmation):
        if password != password_confirmation:
            raise ValidationError({"password_confirmation": "Passwords do not match."})
        hashed = token_hash(token)
        invitation = EmployeeInvitation.objects.select_for_update().filter(token_hash=hashed).first()
        now = timezone.now()
        if not invitation or invitation.used_at or invitation.revoked_at or invitation.expires_at <= now:
            raise ValidationError("Activation link is unavailable.")
        employee = Employee.objects.select_for_update().get(pk=invitation.employee_id)
        if not employee.is_active or employee.status in {"archived", "suspended", "dismissed", "terminated"} or employee.user_id:
            raise ValidationError("Activation link is unavailable.")
        email = invitation.delivery_address.lower().strip()
        if not email:
            raise ValidationError("Activation link is unavailable.")
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Activation link is unavailable.")
        candidate = User(email=email, username=email, first_name=employee.first_name, last_name=employee.last_name, middle_name=employee.middle_name, is_active=True)
        validate_password(password, user=candidate)
        candidate.set_password(password)
        candidate.save()
        employee.user = candidate
        employee.save(update_fields=["user", "updated_at"])
        invitation.used_at = now
        invitation.save(update_fields=["used_at"])
        _event("employee.invitation.used", invitation, candidate, new={"employee_id": str(employee.pk)})
        _event("employee.account.activated", employee, candidate, new={"user_id": candidate.pk})
        return candidate


class RegistrationService:
    GENERIC_MESSAGE = "Заявка принята. Если данные могут быть подтверждены, дальнейшие инструкции будут доступны после проверки."

    @staticmethod
    @transaction.atomic
    def create(*, full_name, email):
        normalized = email.lower().strip()
        existing = RegistrationRequest.objects.filter(email__iexact=normalized, status=RegistrationRequest.Status.PENDING).first()
        if existing:
            return existing, False
        item = RegistrationRequest.objects.create(full_name=full_name.strip(), email=normalized, expires_at=timezone.now() + timedelta(days=settings.REGISTRATION_REQUEST_TTL_DAYS))
        _event("registration.created", item, new={"status": item.status})
        return item, True

    @staticmethod
    @transaction.atomic
    def approve(*, registration, employee, actor_user):
        registration = RegistrationRequest.objects.select_for_update().get(pk=registration.pk)
        if registration.status != RegistrationRequest.Status.PENDING:
            raise ValidationError("Registration was already processed.")
        invitation, raw = InvitationService.issue(employee=employee, actor_user=actor_user, delivery_address=registration.email)
        registration.status = RegistrationRequest.Status.APPROVED
        registration.matched_employee = employee
        registration.reviewed_at = timezone.now()
        registration.reviewed_by = actor_user
        registration.save(update_fields=["status", "matched_employee", "reviewed_at", "reviewed_by"])
        _event("registration.approved", registration, actor_user, new={"employee_id": str(employee.pk)})
        return invitation, raw

    @staticmethod
    @transaction.atomic
    def reject(*, registration, actor_user, reason="rejected"):
        registration = RegistrationRequest.objects.select_for_update().get(pk=registration.pk)
        if registration.status != RegistrationRequest.Status.PENDING:
            raise ValidationError("Registration was already processed.")
        registration.status = RegistrationRequest.Status.REJECTED
        registration.reviewed_at = timezone.now()
        registration.reviewed_by = actor_user
        registration.rejection_code = reason[:80]
        registration.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_code"])
        _event("registration.rejected", registration, actor_user, new={"status": registration.status})
        return registration
