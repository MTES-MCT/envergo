import io
import zipfile
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile

from envergo.utils.validators import detect_mime, validate_mime


def make_png_bytes():
    """Return minimal valid PNG bytes."""
    import struct
    import zlib

    width, height = 1, 1
    raw_data = b"\x00\x00\x00\x00"
    compressed = zlib.compress(raw_data)

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def make_zip_bytes():
    """Return a small valid zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.txt", "hello world")
    return buf.getvalue()


def make_uploaded_file(content, name, content_type):
    """Build an InMemoryUploadedFile from raw bytes."""
    buf = io.BytesIO(content)
    return InMemoryUploadedFile(
        file=buf,
        field_name="file",
        name=name,
        content_type=content_type,
        size=len(content),
        charset=None,
    )


class TestDetectMime:
    def test_detect_png(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        assert detect_mime(uploaded) == "image/png"

    def test_detect_zip(self):
        uploaded = make_uploaded_file(make_zip_bytes(), "archive.zip", "application/zip")
        assert detect_mime(uploaded) == "application/zip"

    def test_detect_plain_text(self):
        uploaded = make_uploaded_file(b"just some text", "note.txt", "text/plain")
        assert detect_mime(uploaded) == "text/plain"


class TestValidateMime:
    def test_allowed_type_passes(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_mime(uploaded, ["image/png"])

    def test_disallowed_type_raises(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        with pytest.raises(ValidationError):
            validate_mime(uploaded, ["application/pdf"])

    def test_zip_passes_when_allowed(self):
        uploaded = make_uploaded_file(make_zip_bytes(), "archive.zip", "application/zip")
        validate_mime(uploaded, ["application/zip"])

    def test_zip_rejected_when_not_allowed(self):
        uploaded = make_uploaded_file(make_zip_bytes(), "archive.zip", "application/zip")
        with pytest.raises(ValidationError):
            validate_mime(uploaded, ["image/png"])

    def test_file_pointer_reset_after_validation(self):
        """File pointer must be at 0 after validation so subsequent code can read it."""
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_mime(uploaded, ["image/png"])
        assert uploaded.tell() == 0
