from unittest.mock import Mock, patch
from urllib.parse import quote, unquote

import pytest
from django.core.exceptions import ImproperlyConfigured
from storages.backends.s3boto3 import S3Boto3Storage

from envergo.utils.storages import (
    LocalFileStorage,
    PrivateMediaStorage,
    PrivateUploadStorage,
    PublicMediaStorage,
    download_source,
)

# Fully offline: the presigning seam (S3Boto3Storage.url) is mocked with canned urls.

ENDPOINT = "https://s3.fr-par.scw.cloud"
BUCKET = "envergo-prod-private"
SIGNED_QUERY = (
    "X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=SCWXXX%2F20260907%2Ffr-par%2Fs3%2Faws4_request"
    "&X-Amz-Date=20260907T120000Z&X-Amz-Expires=3600"
    "&X-Amz-SignedHeaders=host&X-Amz-Signature=abcdef123456"
)


def make_private_storage(cls=PrivateMediaStorage, **kwargs):
    kwargs.setdefault("bucket_name", BUCKET)
    kwargs.setdefault("endpoint_url", ENDPOINT)
    return cls(**kwargs)


def presign(key):
    """A canned path-style presigned URL, as boto3 emits them."""
    return f"{ENDPOINT}/{BUCKET}/{key}?{SIGNED_QUERY}"


class TestPrivateStorageUrl:
    def test_url_rewrites_endpoint_and_bucket_to_proxy_prefix(self):
        storage = make_private_storage()
        canned = presign("media/evaluations/doc.pdf")
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            url = storage.url("evaluations/doc.pdf")
        assert url == f"/fichiers-prives/media/evaluations/doc.pdf?{SIGNED_QUERY}"

    def test_url_preserves_encoded_key_bytes(self):
        # The signature covers the key's exact bytes: the rewrite must not alter one.
        storage = make_private_storage()
        key = "media/pi%C3%A8ce%20%2B1%20%28copie%29.pdf"
        with patch.object(S3Boto3Storage, "url", return_value=presign(key)):
            url = storage.url("pièce +1 (copie).pdf")
        assert url == f"/fichiers-prives/{key}?{SIGNED_QUERY}"

    def test_upload_storage_uses_same_rewrite(self):
        storage = make_private_storage(cls=PrivateUploadStorage)
        canned = presign("upload/requests/REF123/file.pdf")
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            url = storage.url("requests/REF123/file.pdf")
        assert url == f"/fichiers-prives/upload/requests/REF123/file.pdf?{SIGNED_QUERY}"

    def test_virtual_host_style_url_raises(self):
        storage = make_private_storage()
        canned = f"https://{BUCKET}.s3.fr-par.scw.cloud/media/doc.pdf?{SIGNED_QUERY}"
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            with pytest.raises(ImproperlyConfigured):
                storage.url("doc.pdf")

    def test_unexpected_endpoint_raises(self):
        storage = make_private_storage()
        canned = f"https://s3.amazonaws.com/{BUCKET}/media/doc.pdf?{SIGNED_QUERY}"
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            with pytest.raises(ImproperlyConfigured):
                storage.url("doc.pdf")

    def test_s3_url_returns_raw_presigned_url(self):
        storage = make_private_storage()
        canned = presign("media/evaluations/doc.pdf")
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            assert storage.s3_url("evaluations/doc.pdf") == canned

    def test_endpoint_trailing_slash_is_tolerated(self):
        storage = make_private_storage(endpoint_url=f"{ENDPOINT}/")
        canned = presign("media/doc.pdf")
        with patch.object(S3Boto3Storage, "url", return_value=canned):
            url = storage.url("doc.pdf")
        assert url == f"/fichiers-prives/media/doc.pdf?{SIGNED_QUERY}"


class TestPublicStorageUrl:
    def test_url_is_public_proxy_path(self):
        storage = PublicMediaStorage(bucket_name="envergo-prod-public")
        url = storage.url("documents/mémo v2.pdf")
        assert url == "/fichiers/documents/m%C3%A9mo%20v2.pdf"


class TestLocalFileStorage:
    def test_s3_url_aliases_url(self, tmp_path):
        storage = LocalFileStorage(location=str(tmp_path), base_url="/media/")
        assert storage.s3_url("doc.pdf") == storage.url("doc.pdf")
        assert storage.s3_url("doc.pdf") == "/media/doc.pdf"


class TestDownloadSource:
    def test_remote_file_yields_the_s3_url(self):
        signed_url = presign("media/doc.pdf")
        field_file = Mock(spec=["storage", "name", "path"])
        field_file.name = "media/doc.pdf"
        field_file.storage = Mock(spec=["s3_url"])
        field_file.storage.s3_url.return_value = signed_url
        assert download_source(field_file) == signed_url

    def test_local_file_yields_the_filesystem_path(self, tmp_path):
        field_file = Mock(spec=["storage", "name", "path"])
        field_file.name = "doc.pdf"
        field_file.storage = LocalFileStorage(
            location=str(tmp_path), base_url="/media/"
        )
        field_file.path = str(tmp_path / "doc.pdf")
        assert download_source(field_file) == field_file.path


class TestEncodingContract:
    @pytest.mark.parametrize(
        "encoded_key",
        [
            "media/pi%C3%A8ce.pdf",
            "media/mon%20fichier.pdf",
            "media/a%2Bb.pdf",
            "media/100%25.pdf",
            "media/a~b_c-d.pdf",
            "media/l%27arr%C3%AAt%C3%A9%20%281%29.pdf",
        ],
    )
    def test_botocore_encoding_is_quote_canonical_form(self, encoded_key):
        # Pins that botocore's key encoding is quote()'s canonical form, which
        # the view's re-encoding of decoded paths relies on.
        assert quote(unquote(encoded_key), safe="/~") == encoded_key
