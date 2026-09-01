import hashlib
from pathlib import Path

from django.conf import settings


class AttachmentSecurityError(ValueError):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class AttachmentScanner:
    def scan(self, uploaded_file):
        return None


def validate_attachment(uploaded_file, *, max_size=None, allowed_types=None):
    max_size = max_size or settings.ATTACHMENT_MAX_SIZE
    allowed_types = allowed_types or settings.ATTACHMENT_ALLOWED_TYPES
    if not uploaded_file or uploaded_file.size <= 0:
        raise AttachmentSecurityError("Файл пуст.", "attachment_empty")
    if uploaded_file.size > max_size:
        raise AttachmentSecurityError("Файл превышает допустимый размер.", "attachment_too_large")
    content_type = (uploaded_file.content_type or "application/octet-stream").lower()
    if content_type not in allowed_types:
        raise AttachmentSecurityError("Тип файла запрещён политикой безопасности.", "attachment_type_forbidden")
    original = Path(uploaded_file.name).name.strip().replace("\x00", "")
    if not original or len(original) > 255:
        raise AttachmentSecurityError("Некорректное имя файла.", "attachment_filename_invalid")
    forbidden_suffixes = {".exe", ".com", ".bat", ".cmd", ".ps1", ".sh", ".js", ".html", ".htm", ".php", ".svg"}
    if any(suffix.lower() in forbidden_suffixes for suffix in Path(original).suffixes):
        raise AttachmentSecurityError("Расширение файла запрещено политикой безопасности.", "attachment_type_forbidden")
    header = uploaded_file.read(8)
    uploaded_file.seek(0)
    if header.startswith((b"MZ", b"\x7fELF", b"#!")):
        raise AttachmentSecurityError("Исполняемые файлы запрещены.", "attachment_type_forbidden")
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return original, content_type, digest.hexdigest()
