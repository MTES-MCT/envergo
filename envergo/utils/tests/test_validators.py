import io
import zipfile

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

from envergo.utils.validators import detect_mime, validate_mime


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


class TestValidateMime:
    """validate_mime must accept files whose detected MIME type is in the
    allowed list, and reject all others with a ValidationError."""

    def test_allowed_type_passes(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_mime(uploaded, ["image/png"])

    def test_disallowed_type_raises(self):
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        with pytest.raises(ValidationError):
            validate_mime(uploaded, ["application/pdf"])

    def test_zip_passes_when_allowed(self):
        uploaded = make_uploaded_file(
            make_zip_bytes(), "archive.zip", "application/zip"
        )
        validate_mime(uploaded, ["application/zip"])

    def test_zip_rejected_when_not_allowed(self):
        uploaded = make_uploaded_file(
            make_zip_bytes(), "archive.zip", "application/zip"
        )
        with pytest.raises(ValidationError):
            validate_mime(uploaded, ["image/png"])

    def test_spoofed_content_type_is_rejected(self):
        """A file whose declared Content-Type is allowed but whose actual
        content is not must still be rejected. This is the spoofing case the
        validator exists to defend against: here a zip archive is declared as
        image/png, the only allowed type."""
        uploaded = make_uploaded_file(make_zip_bytes(), "archive.zip", "image/png")
        with pytest.raises(ValidationError):
            validate_mime(uploaded, ["image/png"])

    def test_file_pointer_reset_after_validation(self):
        """After validation the file pointer must be back at 0, otherwise
        downstream code (e.g. saving the file to storage) would read an
        empty stream."""
        uploaded = make_uploaded_file(make_png_bytes(), "img.png", "image/png")
        validate_mime(uploaded, ["image/png"])
        assert uploaded.tell() == 0
