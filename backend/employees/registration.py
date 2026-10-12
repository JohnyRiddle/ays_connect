"""Object onboarding. Public credentials never authorize a working API."""
import hashlib
import json
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from access_control.models import EmployeeRole, Role
from access_control.services import RoleService
from organizations.models import Location
from organizations.object_policies import LocationAccessPolicy
from organizations.object_services import object_write, require_available_location
from .models import Employee, EmployeeInvitation, EmployeeObjectResponsibility, RegistrationRequest
from .onboarding import _event, token_hash
from .services import AccountAccessService, EmployeeAssignmentService, EmployeeService

User = get_user_model()
DENIED = "Ссылка или запрос недоступны. Используйте вход или восстановление доступа."
SAFE_OWN = {"people.profile.view_self", "people.onboarding.view_self", "people.change_request.view_self"}
REGISTRATION_LOCATION = {"people.invitation.manage", "people.invitation.delegate", "people.registration.manage"}


def eligible_role(role):
    grants = list(role.permission_grants.select_related("permission"))
    if role.code == "employee_objects_viewer" and {(grant.permission.code, grant.scope) for grant in grants} != {
        ("location.view", "location"), ("people.profile.view_self", "own")
    }:
        return False
    return bool(grants) and all(
        (grant.scope == "own" and grant.permission.code in SAFE_OWN) or
        (grant.scope == "location" and (grant.permission.code.startswith("location.") or
                                       grant.permission.code in REGISTRATION_LOCATION)) for grant in grants)


def existing_user(email):
    return User.objects.annotate(normalized_email=Lower(Trim("email"))).filter(normalized_email=email.strip().lower()).exists()


def email_lock(email):
    # Common boundary for self-registration, invite acceptance and approval.
    if connection.vendor == "postgresql":
        key = int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def public_locations():
    # Ancestors may be closed/archived too. The public projection is UUID + name only.
    qs = Location.objects.filter(node_kind="object", is_active=True, is_archived=False).exclude(
        business_status__in=["final_closed", "seasonal_closed"])
    ids = []
    for item in qs:
        parent, seen, valid = item.parent, {item.pk}, True
        while parent:
            if parent.pk in seen or parent.is_archived or not parent.is_active or parent.business_status in {"final_closed", "seasonal_closed"}:
                valid = False
                break
            seen.add(parent.pk)
            parent = parent.parent
        if valid:
            ids.append(item.pk)
    return qs.filter(pk__in=ids).order_by("name", "pk")


def live_grants(user, permission):
    employee = getattr(user, "employee", None)
    now = timezone.now()
    if not user.is_authenticated or not user.is_active or not employee or not active_employee(employee):
        return EmployeeRole.objects.none()
    return EmployeeRole.objects.filter(employee=employee, is_active=True, role__is_active=True,
        role__permission_grants__permission__code=permission).filter(
        Q(active_from__isnull=True) | Q(active_from__lte=now),
        Q(active_until__isnull=True) | Q(active_until__gt=now)).select_related("role")


def locations_for(user, permission):
    qs = Location.objects.filter(node_kind="object")
    if not user.is_authenticated or not user.is_active:
        return qs.none()
    employee = getattr(user, "employee", None)
    if employee and not active_employee(employee):
        return qs.none()
    if user.is_authenticated and user.is_active and user.is_superuser:
        return qs
    predicate = Q(pk__in=[])
    for grant in live_grants(user, permission):
        for item in grant.role.permission_grants.filter(permission__code=permission):
            if item.scope == "global":
                return qs
            if item.scope == "location" and grant.location_id:
                predicate |= Q(pk=grant.location_id)
            if item.scope == "legal_entity" and grant.legal_entity_id:
                predicate |= Q(legal_entity_id=grant.legal_entity_id)
    return qs.filter(predicate).distinct()


def require(user, permission, location):
    if not locations_for(user, permission).filter(pk=location.pk).exists():
        raise PermissionDenied()


def validate_plan(actor, location, plan):
    allowed = {"role", "access_locations", "responsibility_locations", "responsibility_mode"}
    if set(plan) - allowed:
        raise ValidationError("Неподдерживаемый план доступа.")
    role = Role.objects.filter(pk=plan.get("role"), is_active=True).first()
    if not role:
        raise ValidationError("Выберите действующую роль.")
    access = list(dict.fromkeys(plan.get("access_locations", [str(location.pk)])))
    responsible = list(dict.fromkeys(plan.get("responsibility_locations", [])))
    mode = plan.get("responsibility_mode", "selected")
    if mode not in {"selected", "all"} or (mode == "all" and responsible):
        raise ValidationError("Неверная область ответственности.")
    if mode == "all":
        if not (actor.is_active and actor.is_superuser):
            # All is instance-wide and requires explicit global authority, not a location grant.
            if not live_grants(actor, "people.responsibility.all").filter(
                role__permission_grants__permission__code="people.responsibility.all",
                role__permission_grants__scope="global").exists():
                raise PermissionDenied()
    ids = set(access + responsible + [str(location.pk)])
    if len(ids) > 100:
        raise ValidationError("Слишком много объектов.")
    available = public_locations().filter(pk__in=ids)
    if available.count() != len(ids):
        raise ValidationError("Объект недоступен.")
    for obj in available:
        require_available_location(obj)
        require(actor, "people.invitation.delegate", obj)
    if not eligible_role(role):
        raise ValidationError("Пилот поддерживает объектные полномочия и проверенный собственный просмотр; глобальные и legacy grants назначаются отдельно.")
    if not access:
        raise ValidationError("Укажите область доступа.")
    # Exact role/context is a conservative subset proof, never a permission name heuristic.
    if not actor.is_superuser:
        for pk in access:
            if not live_grants(actor, "people.invitation.delegate").exists():
                raise PermissionDenied()
            now = timezone.now()
            if not EmployeeRole.objects.filter(employee=actor.employee, role=role, is_active=True,
                location_id=pk).filter(Q(active_from__isnull=True) | Q(active_from__lte=now),
                Q(active_until__isnull=True) | Q(active_until__gt=now)).exists():
                raise PermissionDenied("Роль и scope нельзя делегировать.")
    return {"role": str(role.pk), "access_locations": access,
            "responsibility_mode": mode, "responsibility_locations": responsible}


def signed_token(entity, purpose, generation):
    # Deterministic signed capabilities can be reconstructed for retry delivery;
    # only their SHA-256 is persisted for invites, never raw tokens in mail jobs.
    return signing.Signer(salt="ays.registration." + purpose).sign(f"{entity.pk}:{generation}")


def permission_snapshot(role):
    rows = list(role.permission_grants.order_by("permission__code", "scope").values_list("permission__code", "scope"))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def verification_token(item):
    return signed_token(item, "verify", item.mail_generation)


def queue_mail(item, kind, actor=None):
    _event("registration.mail.requested", item, actor, new={"kind": kind, "generation": item.mail_generation})


def active_employee(employee):
    return employee.is_active and employee.status not in {"archived", "suspended", "dismissed", "terminated", "inactive"}


class ObjectRegistrationService:
    @staticmethod
    @transaction.atomic
    def submit(*, email, first_name, last_name, middle_name, location, password, password_confirmation, invitation=None):
        email = email.strip().lower()
        if len(" ".join(filter(None, [last_name, first_name, middle_name]))) > 300:
            raise ValidationError("ФИО не должно превышать 300 символов.")
        if password != password_confirmation:
            raise ValidationError({"password_confirmation": "Пароли не совпадают."})
        candidate = User(email=email, username=email, first_name=first_name, last_name=last_name)
        try:
            validate_password(password, candidate)
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from exc
        email_lock(email)
        returning = invitation and invitation.employee_id and invitation.employee.user_id and not invitation.employee.user.is_active and active_employee(invitation.employee) and invitation.employee.account_access_state == "reactivation_required" and invitation.employee.user.email.strip().lower() == email
        if existing_user(email) and not returning:
            # No account/employment disclosure, no automatic reactivation.
            return None, secrets.token_urlsafe(32)
        if invitation:
            if invitation.employee_id:
                employee = Employee.objects.select_for_update().get(pk=invitation.employee_id)
            invitation = EmployeeInvitation.objects.select_for_update().get(pk=invitation.pk)
            ObjectInvitationService.available(invitation)
            if invitation.delivery_address and email != invitation.delivery_address.strip().lower():
                raise ValidationError(DENIED)
            location = invitation.employment_location
            if invitation.employee_id:
                employee = Employee.objects.select_for_update().get(pk=invitation.employee_id)
                if not active_employee(employee) or (employee.user_id and not returning):
                    raise ValidationError(DENIED)
        with object_write():
            if not public_locations().filter(pk=location.pk).exists():
                raise ValidationError("Объект недоступен для регистрации.")
            require_available_location(location)
            for expired in RegistrationRequest.objects.select_for_update().filter(email__iexact=email,
                    status__in=["pending", "email_pending"], expires_at__lte=timezone.now()):
                expired.status = "expired"
                expired.password_hash = ""
                expired.save(update_fields=["status", "password_hash"])
                _event("registration.expired", expired, new={"status": "expired"})
            existing = RegistrationRequest.objects.filter(email__iexact=email,
                status__in=["pending", "email_pending"]).first()
            if existing or (invitation and RegistrationRequest.objects.filter(invitation=invitation).exists()):
                # Never overwrite identity/password from an unauthenticated repeat.
                # A repeat gets an unrelated capability, while the genuine email owner
                # can recover the true status capability from the confirmation email.
                return None, secrets.token_urlsafe(32)
            status_key = secrets.token_urlsafe(32)
            item = RegistrationRequest.objects.create(email=email, first_name=first_name,
                last_name=last_name, middle_name=middle_name,
                full_name=" ".join(filter(None, [last_name, first_name, middle_name])),
                status="email_pending", employment_location=location, invitation=invitation,
                password_hash=make_password(password), status_token_hash=token_hash(status_key),
                expires_at=timezone.now() + timedelta(days=14))
            _event("registration.submitted", item, new={"location_id": str(location.pk), "status": item.status})
            queue_mail(item, "verify")
            return item, status_key

    @staticmethod
    @transaction.atomic
    def confirm(*, token):
        try:
            value = signing.Signer(salt="ays.registration.verify").unsign(token)
            pk, generation = value.split(":")
        except (signing.BadSignature, ValueError):
            raise ValidationError(DENIED)
        item = RegistrationRequest.objects.filter(pk=pk).first()
        if not item:
            raise ValidationError(DENIED)
        email_lock(item.email)
        if item.invitation_id and item.invitation.employee_id:
            Employee.objects.select_for_update().get(pk=item.invitation.employee_id)
            EmployeeInvitation.objects.select_for_update().get(pk=item.invitation_id)
        item = RegistrationRequest.objects.select_for_update().get(pk=pk)
        if str(item.mail_generation) != generation or item.expires_at <= timezone.now() or item.status not in {"email_pending", "pending", "approved"}:
            raise ValidationError(DENIED)
        if item.status == "email_pending":
            if not public_locations().filter(pk=item.employment_location_id).exists():
                raise ValidationError(DENIED)
            item.status = "pending"
            item.email_confirmed_at = timezone.now()
            item.save(update_fields=["status", "email_confirmed_at"])
            _event("registration.email_confirmed", item, new={"status": item.status})
            if item.invitation_id:
                ObjectRegistrationService.approve(registration=item, actor=item.invitation.created_by,
                    plan=item.invitation.access_plan, automatic=True)
            else:
                queue_mail(item, "review")
        # Email proof also returns a new status capability, without exposing it in URLs/logs.
        raw = secrets.token_urlsafe(32)
        item.status_token_hash = token_hash(raw)
        item.save(update_fields=["status_token_hash"])
        item.refresh_from_db()
        return item, raw

    @staticmethod
    @transaction.atomic
    def approve(*, registration, actor, plan, employee=None, automatic=False):
        email_lock(registration.email)
        if automatic and registration.invitation_id:
            if registration.invitation.employee_id:
                employee = Employee.objects.select_for_update().get(pk=registration.invitation.employee_id)
            invitation = EmployeeInvitation.objects.select_for_update().get(pk=registration.invitation_id)
        if employee:
            employee = Employee.objects.select_for_update().get(pk=employee.pk)
        item = RegistrationRequest.objects.select_for_update().get(pk=registration.pk)
        if item.invitation_id and not automatic:
            raise ValidationError("Приглашение принимается через подтверждение e-mail.")
        location = item.employment_location
        if item.status != "pending" or not item.email_confirmed_at or item.expires_at <= timezone.now():
            raise ValidationError(DENIED)
        if automatic:
            invitation = EmployeeInvitation.objects.select_for_update().get(pk=item.invitation_id)
            ObjectInvitationService.available(invitation)
            if invitation.employee_id:
                employee = Employee.objects.select_for_update().get(pk=invitation.employee_id)
        else:
            require(actor, "people.registration.manage", location)
        with object_write():
            normalized = validate_plan(actor, location, plan)
            returning = employee and employee.user_id and not employee.user.is_active and employee.account_access_state == "reactivation_required" and employee.user.email.strip().lower() == item.email
            if existing_user(item.email) and not returning:
                raise ValidationError(DENIED)
            if employee:
                if not active_employee(employee) or (employee.user_id and not returning):
                    raise ValidationError("Используйте штатный lifecycle возвращения сотрудника.")
                # Explicit authorized linking, never name matching.
                from .onboarding_api import visible_employees
                if not actor.is_superuser and not visible_employees(actor, "people.employee.manage").filter(pk=employee.pk).exists():
                    raise PermissionDenied()
            elif Employee.objects.filter(Q(work_email__iexact=item.email) | Q(user__email__iexact=item.email)).exists():
                raise ValidationError("Требуется явное решение о привязке сотрудника.")
            else:
                employee = EmployeeService.create(actor_user=actor, first_name=item.first_name,
                    last_name=item.last_name, middle_name=item.middle_name, work_email=item.email)
            if returning:
                if employee.user.is_staff or employee.user.is_superuser or employee.user.role_assignments.exists():
                    raise ValidationError("Привилегированный или legacy-аккаунт возвращается через отдельный account lifecycle.")
                from access_control.services import PermissionService
                if not actor.is_superuser and not PermissionService.has_permission(employee=actor.employee,
                        permission="people.account_access.reactivate", obj=employee):
                    raise PermissionDenied()
                for previous_grant in employee.access_roles.filter(is_active=True):
                    RoleService.revoke_role(assignment=previous_grant, actor_user=actor)
                user = employee.user
                user.password = item.password_hash
                user.save(update_fields=["password"])
                AccountAccessService.set_access(employee=employee, actor_user=actor, enabled=True, action="reactivated")
            else:
                user = User.objects.create(email=item.email, username="registration-" + uuid.uuid4().hex,
                    first_name=employee.first_name, last_name=employee.last_name, middle_name=employee.middle_name,
                    password=item.password_hash, is_active=True)
            employee.user = user
            employee.save(update_fields=["user", "updated_at"])
            EmployeeAssignmentService.replace_primary(employee=employee, actor_user=actor,
                location=location, position=employee.position_ref,
                legal_entity=employee.legal_entity, org_unit=employee.org_unit)
            role = Role.objects.get(pk=normalized["role"])
            for pk in normalized["access_locations"]:
                RoleService.assign_role(employee=employee, role=role, actor_user=actor, location_id=pk)
            ResponsibilityService.replace(employee=employee, actor=actor,
                mode=normalized["responsibility_mode"], locations=normalized["responsibility_locations"])
            item.matched_employee = employee
            item.status = "approved"
            item.reviewed_by = actor
            item.reviewed_at = timezone.now()
            item.password_hash = ""
            item.save(update_fields=["matched_employee", "status", "reviewed_by", "reviewed_at", "password_hash"])
            if item.invitation_id:
                invitation.used_at = timezone.now()
                invitation.accepted_by = user
                invitation.employee = employee
                invitation.status = "accepted"
                invitation.save(update_fields=["used_at", "accepted_by", "employee", "status"])
                _event("people.invitation.accepted", invitation, actor, new={"employee_id": str(employee.pk)})
            _event("registration.approved", item, actor, new={"employee_id": str(employee.pk), "user_id": user.pk, "access_plan": normalized})
            _event("people.user.linked", employee, actor, new={"user_id": user.pk})
            queue_mail(item, "approved", actor)
            return item

    @staticmethod
    @transaction.atomic
    def reject(*, registration, actor, reason):
        item = RegistrationRequest.objects.select_for_update().get(pk=registration.pk)
        require(actor, "people.registration.manage", item.employment_location)
        if item.status != "pending" or not reason.strip():
            raise ValidationError("Укажите причину для ожидающей согласования заявки.")
        item.status = "rejected"
        item.rejection_code = reason[:80]
        item.reviewed_by = actor
        item.reviewed_at = timezone.now()
        item.password_hash = ""
        item.save(update_fields=["status", "rejection_code", "reviewed_by", "reviewed_at", "password_hash"])
        _event("registration.rejected", item, actor, new={"reason": item.rejection_code})
        queue_mail(item, "rejected", actor)
        return item


class ObjectInvitationService:
    @staticmethod
    def available(invitation):
        if not invitation.employment_location_id or invitation.used_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
            raise ValidationError(DENIED)
        if not public_locations().filter(pk=invitation.employment_location_id).exists():
            raise ValidationError(DENIED)
        require(invitation.created_by, "people.invitation.manage", invitation.employment_location)
        validate_plan(invitation.created_by, invitation.employment_location, invitation.access_plan)
        role = Role.objects.get(pk=invitation.access_plan["role"])
        if permission_snapshot(role) != invitation.permission_snapshot:
            raise ValidationError("Состав роли изменился: перевыпустите приглашение.")

    @staticmethod
    @transaction.atomic
    def issue(*, actor, location, plan=None, email="", employee=None, days=7):
        if employee:
            employee = Employee.objects.select_for_update().get(pk=employee.pk)
            if not active_employee(employee) or (employee.user_id and (employee.user.is_active or employee.account_access_state != "reactivation_required")):
                raise ValidationError(DENIED)
        require(actor, "people.invitation.manage", location)
        with object_write():
            if plan is None:
                role = Role.objects.filter(code="employee_objects_viewer", is_active=True).first()
                if not role:
                    raise ValidationError("Минимальная роль не настроена.")
                plan = {"role": str(role.pk), "access_locations": [str(location.pk)]}
            normalized = validate_plan(actor, location, plan)
            if not 1 <= days <= 7:
                raise ValidationError("Срок: от 1 до 7 дней.")
            if employee:
                from .onboarding import InvitationService
                for previous in employee.invitations.filter(used_at__isnull=True, revoked_at__isnull=True):
                    InvitationService.revoke(invitation=previous, actor_user=actor, reason="superseded")
            item = EmployeeInvitation.objects.create(employee=employee, employment_location=location,
                access_plan=normalized, delivery_address=email.strip().lower(), token_hash=secrets.token_hex(32),
                permission_snapshot=permission_snapshot(Role.objects.get(pk=normalized["role"])),
                created_by=actor, expires_at=timezone.now() + timedelta(days=days))
            token = signed_token(item, "invite", item.version)
            item.token_hash = token_hash(token)
            item.save(update_fields=["token_hash"])
            _event("people.invitation.created", item, actor, new={"location_id": str(location.pk), "access_plan": normalized})
            if item.delivery_address:
                _event("registration.invite_mail.requested", item, actor, new={"generation": item.version})
            return item, token

    @staticmethod
    def context(token):
        item = EmployeeInvitation.objects.filter(token_hash=token_hash(token), employment_location__isnull=False).first()
        if not item:
            raise ValidationError(DENIED)
        with transaction.atomic(), object_write():
            ObjectInvitationService.available(item)
        return item


class ResponsibilityService:
    @staticmethod
    def end(employee, actor):
        for item in employee.object_responsibility_history.select_for_update().filter(valid_to__isnull=True):
            item.valid_to = timezone.now()
            item.save(update_fields=["valid_to"])
            _event("people.responsibility.ended", item, actor, new={"employee_id": str(employee.pk), "valid_to": item.valid_to})

    @staticmethod
    @transaction.atomic
    def replace(*, employee, actor, mode, locations):
        locations = [str(pk) for pk in locations]
        if not actor.is_authenticated or not actor.is_active or (getattr(actor, "employee", None) and not active_employee(actor.employee)):
            raise PermissionDenied()
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        if not active_employee(employee):
            raise ValidationError(DENIED)
        if mode not in {"all", "selected"} or (mode == "all" and locations):
            raise ValidationError("Неверная ответственность.")
        if mode == "all" and not (actor.is_superuser and actor.is_active) and not live_grants(actor, "people.responsibility.all").filter(
            role__permission_grants__permission__code="people.responsibility.all", role__permission_grants__scope="global").exists():
            raise PermissionDenied()
        with object_write():
            for pk in set(locations):
                obj = Location.objects.get(pk=pk)
                require_available_location(obj)
                if obj.node_kind != "object" or obj.business_status in {"final_closed", "seasonal_closed"}:
                    raise ValidationError("Объект недоступен.")
                require(actor, "people.invitation.delegate", obj)
            ResponsibilityService.end(employee, actor)
            item = EmployeeObjectResponsibility.objects.create(employee=employee, mode=mode, changed_by=actor)
            item.locations.set(locations)
            _event("people.responsibility.changed", item, actor, new={"employee_id": str(employee.pk), "mode": mode, "locations": locations})
            return item

    @staticmethod
    def effective(employee):
        if not active_employee(employee):
            return Location.objects.none()
        item = employee.object_responsibility_history.filter(valid_to__isnull=True).first()
        if not item:
            return Location.objects.none()
        return public_locations() if item.mode == "all" else public_locations().filter(pk__in=item.locations.values("pk"))
