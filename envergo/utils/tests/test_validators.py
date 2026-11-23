import io
import zipfile

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

from envergo.utils.validators import detect_mime, validate_file_type


def make_png_bytes():
    """Build a minimal valid PNG file (1×1 red pixel).

    Constructs the binary manually rather than depending on Pillow, so the
    test stays self-contained. The structure follows the PNG spec: signature,
    then IHDR / IDAT / IEND chunks, each with a CRC-32 trailer.
    """
    import struct
    import zlib

    width, height = 1, 1
    # One row: filter byte (0 = None) + 3 bytes RGB
    raw_data = b"\x00\xff\x00\x00"
    compressed = zlib.compress(raw_data)

    def chunk(chunk_type, data):
        """Wrap *data* in a PNG chunk: length + type + data + CRC."""
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    # IHDR: width, height, bit-depth 8, colour-type 2 (RGB), compression 0,
    # filter 0, interlace 0
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
    """Wrap raw bytes in a Django InMemoryUploadedFile.

    The content_type is the browser-declared MIME type — it is NOT what
    detect_mime should return, since detect_mime inspects actual file content
    via libmagic. We set it here because Django's UploadedFile requires it.
    """
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
    """detect_mime must identify MIME types from actual file content, not from
    the filename or the browser-declared Content-Type header."""

    def test_detect_png(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        assert detect_mime(uploaded) == "image/png"

    def test_detect_zip(self):
        """Zip detection is the reason detect_mime uses from_file instead of
        from_buffer — libmagic's buffer path cannot detect zip because its
        central directory is at the end of the file."""
        uploaded = make_uploaded_file(
            make_zip_bytes(), "archive.zip", "application/zip"
        )
        assert detect_mime(uploaded) == "application/zip"

    def test_detect_plain_text(self):
        uploaded = make_uploaded_file(b"just some text", "note.txt", "text/plain")
        assert detect_mime(uploaded) == "text/plain"

    def test_detect_ignores_declared_content_type(self):
        """Detection must rely on file content, not the browser-declared
        Content-Type. Here PNG bytes are deliberately mislabeled as a PDF;
        detect_mime must still return the real type sniffed from the bytes."""
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "application/pdf")
        assert detect_mime(uploaded) == "image/png"


class TestValidateFileType:
    """validate_file_type must accept a file only if its extension is allowed and its content matches that extension."""

    ALLOWED = {
        ".png": {"image/png"},
        ".zip": {"application/zip"},
    }

    def test_matching_extension_and_content_passes(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_file_type(uploaded, self.ALLOWED)

    def test_extension_is_case_insensitive(self):
        uploaded = make_uploaded_file(make_png_bytes(), "IMG.PNG", "image/png")
        validate_file_type(uploaded, self.ALLOWED)

    def test_allowed_content_under_another_allowed_extension_is_rejected(self):
        """Both png and zip are allowed, but a png must not be stored as a zip."""
        uploaded = make_uploaded_file(make_png_bytes(), "img.zip", "application/zip")
        with pytest.raises(ValidationError):
            validate_file_type(uploaded, self.ALLOWED)

    def test_allowed_content_under_disallowed_extension_is_rejected(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.html", "text/html")
        with pytest.raises(ValidationError):
            validate_file_type(uploaded, self.ALLOWED)

    def test_missing_extension_is_rejected(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img", "image/png")
        with pytest.raises(ValidationError):
            validate_file_type(uploaded, self.ALLOWED)

    def test_file_pointer_reset_after_validation(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_file_type(uploaded, self.ALLOWED)
        assert uploaded.tell() == 0
