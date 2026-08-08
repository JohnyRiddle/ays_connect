from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.services import record
from .models import MaterialAcknowledgmentAssignment, MaterialVersion


ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
ALLOWED_MIME_PREFIXES = ("application/pdf", "application/msword", "application/vnd.", "image/", "video/")


def validate_material_file(uploaded):
    if not uploaded:
        return
    limit = settings.KNOWLEDGE_MAX_FILE_SIZE_MB * 1024 * 1024
    if uploaded.size > limit:
        raise ValidationError({"file": f"Максимальный размер файла — {settings.KNOWLEDGE_MAX_FILE_SIZE_MB} МБ"})
    if Path(uploaded.name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError({"file": "Неподдерживаемое расширение файла"})
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if content_type and not content_type.startswith(ALLOWED_MIME_PREFIXES):
        raise ValidationError({"file": "Неподдерживаемый MIME-тип файла"})


@transaction.atomic
def publish_version(*, material, actor, data, request=None):
    uploaded = data.get("file")
    validate_material_file(uploaded)
    next_version = (material.versions.order_by("-version").values_list("version", flat=True).first() or 0) + 1
    material.versions.filter(is_current=True).update(is_current=False)
    version = MaterialVersion.objects.create(
        material=material,
        version=next_version,
        title=data.get("title") or material.title,
        description=data.get("description", ""),
        file=uploaded or "",
        original_name=uploaded.name if uploaded else "",
        content_type=getattr(uploaded, "content_type", "") if uploaded else "",
        size=uploaded.size if uploaded else 0,
        external_url=data.get("external_url", ""),
        content=data.get("content", ""),
        change_summary=data.get("change_summary", ""),
        created_by=actor,
        effective_from=data.get("effective_from"),
        is_current=True,
        requires_reacknowledgment=bool(data.get("requires_reacknowledgment", False)),
    )
    material.current_version = version
    material.status = material.Status.PUBLISHED
    material.published_at = timezone.now()
    material.save(update_fields=["current_version", "status", "published_at", "updated_at"])
    if version.requires_reacknowledgment:
        prior_employee_ids = MaterialAcknowledgmentAssignment.objects.filter(
            version__material=material
        ).values_list("employee_id", flat=True).distinct()
        MaterialAcknowledgmentAssignment.objects.bulk_create([
            MaterialAcknowledgmentAssignment(version=version, employee_id=employee_id, assigned_by=actor)
            for employee_id in prior_employee_ids
        ], ignore_conflicts=True)
    record(actor, "knowledge.version_published", version, new_values={"material_id": material.id, "version": next_version}, request=request)
    return version
