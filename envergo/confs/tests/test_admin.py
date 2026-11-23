import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from envergo.confs.admin import HostedFileAdminForm

pytestmark = pytest.mark.django_db


def file_errors(upload):
    form = HostedFileAdminForm(data={}, files={"file": upload})
    form.is_valid()
    return form.errors.get("file")


def test_hosted_file_accepts_pdf():
    assert not file_errors(SimpleUploadedFile("doc.pdf", b"%PDF-1.4\n%%EOF"))


def test_hosted_file_accepts_html():
    html = b"<!DOCTYPE html><html><body>Hello</body></html>"
    assert not file_errors(SimpleUploadedFile("page.html", html))


def test_hosted_file_rejects_content_not_matching_extension():
    assert file_errors(SimpleUploadedFile("page.html", b"%PDF-1.4\n%%EOF"))


def test_hosted_file_rejects_svg():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert file_errors(SimpleUploadedFile("image.svg", svg))
