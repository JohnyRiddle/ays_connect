from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .attachments import AttachmentSecurityError, validate_attachment


class AttachmentSignatureHardeningTests(SimpleTestCase):
    def rejected(self,name,content):
        with self.assertRaises(AttachmentSecurityError): validate_attachment(SimpleUploadedFile(name,content,content_type="text/plain"))

    def test_elf_is_rejected_despite_allowed_mime(self): self.rejected("notes.txt",b"\x7fELFpayload")
    def test_shebang_is_rejected_despite_allowed_mime(self): self.rejected("notes.txt",b"#!/bin/sh")
    def test_double_executable_extension_is_rejected(self): self.rejected("invoice.exe.txt",b"not executable")

    def test_all_script_and_executable_suffix_positions_are_rejected(self):
        for name in ("tool.exe", "tool.exe.pdf", "tool.pdf.exe", "tool.cmd", "tool.bat", "tool.ps1", "tool.js"):
            with self.subTest(name=name): self.rejected(name, b"payload")

    def test_invalid_mime_and_oversize_are_rejected(self):
        with self.assertRaises(AttachmentSecurityError) as invalid_mime:
            validate_attachment(SimpleUploadedFile("safe.txt", b"payload", content_type="application/x-msdownload"))
        self.assertEqual(invalid_mime.exception.code, "attachment_type_forbidden")
        with self.assertRaises(AttachmentSecurityError) as oversized:
            validate_attachment(SimpleUploadedFile("safe.txt", b"12345", content_type="text/plain"), max_size=4)
        self.assertEqual(oversized.exception.code, "attachment_too_large")
