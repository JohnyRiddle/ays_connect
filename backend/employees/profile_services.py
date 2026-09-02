import io
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from audit.services import AuditService
from events.services import DomainEventService
from .models import Employee, EmployeeDataChangeRequest, EmployeeProfile, TeamMembership


PROFILE_FIELDS = {"preferred_name", "bio", "additional_email", "additional_phone", "timezone", "preferred_language"}
VISIBILITY_FIELDS = {"bio_visibility", "additional_email_visibility", "additional_phone_visibility"}


def _emit(action, entity, actor, safe):
    AuditService.record(action=action, entity=entity, actor_user=actor, new_value=safe)
    DomainEventService.publish(event_type=action, entity=entity, actor=actor, payload=safe)
    notification_reasons={
        "people.data_change_request.approved":"PEOPLE_CHANGE_APPROVED",
        "people.data_change_request.rejected":"PEOPLE_CHANGE_REJECTED",
        "people.data_change_request.applied":"PEOPLE_CHANGE_APPLIED",
        "people.data_change_request.failed":"PEOPLE_CHANGE_FAILED",
    }
    if action in notification_reasons and getattr(entity,"employee_id",None):
        DomainEventService.publish(event_type="notification.requested",entity=entity,actor=actor,payload={"reason":notification_reasons[action],"recipient_employee_id":str(entity.employee_id),"change_request_id":str(entity.pk),"field_type":entity.field_type})


def ensure_profile(employee, actor=None):
    profile, created = EmployeeProfile.objects.get_or_create(employee=employee)
    if created:
        _emit("people.profile.created", profile, actor, {"employee_id": str(employee.pk)})
    return profile


def completeness(employee, profile=None):
    profile = profile or ensure_profile(employee)
    values = {"preferred_name": profile.preferred_name, "bio": profile.bio, "additional_contact": profile.additional_email or profile.additional_phone, "timezone": profile.timezone}
    completed = [key for key, value in values.items() if value]
    missing = [key for key in values if key not in completed]
    return {"percentage": round(len(completed) * 100 / len(values)), "completed_fields": completed, "missing_fields": missing, "available_actions": ["update_profile", "upload_avatar"]}


class ProfileService:
    @staticmethod
    @transaction.atomic
    def update(employee, actor, expected_version, changes):
        invalid = set(changes) - PROFILE_FIELDS
        if invalid: raise ValidationError(f"Unsupported profile fields: {', '.join(sorted(invalid))}")
        profile = EmployeeProfile.objects.select_for_update().get(employee=employee)
        if profile.version != expected_version: raise ValidationError("Profile version is stale.")
        if "additional_email" in changes and changes["additional_email"]: validate_email(changes["additional_email"])
        if "timezone" in changes:
            try: ZoneInfo(changes["timezone"])
            except ZoneInfoNotFoundError as exc: raise ValidationError("Unknown IANA timezone.") from exc
        for key, value in changes.items(): setattr(profile, key, value)
        profile.version += 1; profile.save(update_fields=[*changes, "version", "updated_at"])
        _emit("people.profile.updated", profile, actor, {"employee_id": str(employee.pk), "fields": sorted(changes)})
        return profile

    @staticmethod
    @transaction.atomic
    def visibility(employee, actor, expected_version, changes):
        if set(changes) - VISIBILITY_FIELDS: raise ValidationError("Unknown visibility field.")
        profile = EmployeeProfile.objects.select_for_update().get(employee=employee)
        if profile.version != expected_version: raise ValidationError("Profile version is stale.")
        allowed = set(EmployeeProfile.Visibility.values)
        if any(value not in allowed for value in changes.values()): raise ValidationError("Unknown visibility level.")
        for key, value in changes.items(): setattr(profile, key, value)
        profile.version += 1; profile.save(update_fields=[*changes, "version", "updated_at"])
        _emit("people.profile.visibility_changed", profile, actor, {"employee_id": str(employee.pk), "fields": sorted(changes)})
        return profile

    @staticmethod
    @transaction.atomic
    def avatar(employee, actor, uploaded):
        if not uploaded or uploaded.size < 1 or uploaded.size > 5 * 1024 * 1024: raise ValidationError("Avatar must be 1 byte to 5 MB.")
        content = uploaded.read(); uploaded.seek(0)
        try:
            Image.MAX_IMAGE_PIXELS=25_000_000
            image=Image.open(io.BytesIO(content));kind=(image.format or "").lower();image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValidationError("Avatar image is damaged or unsupported.") from exc
        if kind not in {"jpeg", "png", "webp"}: raise ValidationError("Only valid JPEG, PNG or WebP images are allowed.")
        locked = Employee.objects.select_for_update().get(pk=employee.pk); old_name = locked.avatar.name if locked.avatar else ""
        extension = "jpg" if kind == "jpeg" else kind
        locked.avatar.save(f"{locked.pk}.{extension}", ContentFile(content), save=False); locked.save(update_fields=["avatar", "updated_at"])
        if old_name and old_name != locked.avatar.name: transaction.on_commit(lambda: locked.avatar.storage.delete(old_name))
        _emit("people.profile.avatar_changed", locked, actor, {"employee_id": str(locked.pk), "format": kind, "size": len(content)})
        return locked

    @staticmethod
    @transaction.atomic
    def remove_avatar(employee, actor):
        locked = Employee.objects.select_for_update().get(pk=employee.pk); old_name = locked.avatar.name if locked.avatar else ""
        locked.avatar = None; locked.save(update_fields=["avatar", "updated_at"])
        if old_name: transaction.on_commit(lambda: locked.avatar.storage.delete(old_name))
        _emit("people.profile.avatar_removed", locked, actor, {"employee_id": str(locked.pk)})


class ChangeRequestService:
    @staticmethod
    def snapshot(employee, field_type):
        if field_type == "legal_name": return {"first_name": employee.first_name, "last_name": employee.last_name, "middle_name": employee.middle_name}
        return {"value": getattr(employee, field_type)}

    @staticmethod
    def validate(field_type, value):
        if field_type not in EmployeeDataChangeRequest.FieldType.values: raise ValidationError("Unsupported field type.")
        if field_type == "legal_name":
            if set(value) != {"first_name", "last_name", "middle_name"} or not value["first_name"] or not value["last_name"]: raise ValidationError("Provide first_name, last_name and middle_name.")
            return value
        raw = str(value.get("value", "")).strip()
        if field_type == "work_email": validate_email(raw)
        if field_type == "work_phone" and not re.fullmatch(r"[+0-9() -]{5,40}", raw): raise ValidationError("Invalid phone.")
        return {"value": raw}

    @classmethod
    @transaction.atomic
    def submit(cls, employee, actor, field_type, value, reason):
        value = cls.validate(field_type, value)
        if not reason or not reason.strip(): raise ValidationError("Reason is required.")
        item = EmployeeDataChangeRequest.objects.create(employee=employee, field_type=field_type, requested_value=value, current_value_snapshot=cls.snapshot(employee, field_type), reason=reason)
        _emit("people.data_change_request.submitted", item, actor, {"employee_id": str(employee.pk), "field_type": field_type})
        return item

    @staticmethod
    @transaction.atomic
    def transition(item, actor, expected_version, target, comment=""):
        locked = EmployeeDataChangeRequest.objects.select_for_update().select_related("employee").get(pk=item.pk)
        if locked.version != expected_version: raise ValidationError("Change request version is stale.")
        if locked.employee.user_id == getattr(actor, "pk", None) and target in {"approved", "rejected"}: raise ValidationError("Self-review is forbidden.")
        allowed = {"approved", "rejected"} if locked.status == "submitted" else set()
        if target not in allowed: raise ValidationError("Invalid status transition.")
        locked.status=target; locked.reviewed_by=actor; locked.reviewed_at=timezone.now(); locked.review_comment=comment; locked.version += 1; locked.save()
        _emit(f"people.data_change_request.{target}", locked, actor, {"employee_id": str(locked.employee_id), "field_type": locked.field_type})
        return locked

    @staticmethod
    @transaction.atomic
    def cancel(item, actor, expected_version):
        locked=EmployeeDataChangeRequest.objects.select_for_update().get(pk=item.pk, employee__user=actor)
        if locked.version != expected_version or locked.status != "submitted": raise ValidationError("Change request cannot be cancelled.")
        locked.status="cancelled"; locked.version+=1; locked.save(update_fields=["status","version","updated_at"])
        _emit("people.data_change_request.cancelled",locked,actor,{"employee_id":str(locked.employee_id),"field_type":locked.field_type}); return locked

    @classmethod
    @transaction.atomic
    def apply(cls, item, actor, expected_version):
        locked=EmployeeDataChangeRequest.objects.select_for_update().select_related("employee").get(pk=item.pk)
        if locked.status == "applied": return locked
        if locked.version != expected_version or locked.status != "approved": raise ValidationError("Change request cannot be applied.")
        employee=Employee.objects.select_for_update().get(pk=locked.employee_id)
        if cls.snapshot(employee,locked.field_type) != locked.current_value_snapshot:
            locked.status="failed";locked.review_comment="stale_snapshot";locked.version+=1;locked.save(update_fields=["status","review_comment","version","updated_at"])
            _emit("people.data_change_request.failed",locked,actor,{"employee_id":str(employee.pk),"field_type":locked.field_type,"error_code":"stale_snapshot"});return locked
        if locked.field_type=="legal_name":
            for key,value in locked.requested_value.items(): setattr(employee,key,value)
            fields=["first_name","last_name","middle_name"]
        else: setattr(employee,locked.field_type,locked.requested_value["value"]); fields=[locked.field_type]
        employee.save(update_fields=[*fields,"updated_at"]); locked.status="applied"; locked.applied_at=timezone.now(); locked.version+=1; locked.save()
        _emit("people.data_change_request.applied",locked,actor,{"employee_id":str(employee.pk),"field_type":locked.field_type}); return locked


def can_see(profile, field, viewer, subject):
    if viewer.is_superuser or viewer.pk == subject.user_id: return True
    level=getattr(profile,f"{field}_visibility")
    actor=getattr(viewer,"employee",None)
    if not actor or not actor.is_active: return False
    if level=="organization": return actor.legal_entity_id == subject.legal_entity_id
    if level=="managers":
        cursor=subject.manager
        while cursor:
            if cursor.pk==actor.pk:return True
            cursor=cursor.manager
    if level=="team":
        teams=TeamMembership.objects.filter(employee=subject,valid_to__isnull=True).values("team_id")
        return TeamMembership.objects.filter(employee=actor,team_id__in=teams,valid_to__isnull=True).exists()
    return False
