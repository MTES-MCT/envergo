import os

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from envergo.confs.models import HostedFile
from envergo.users.tests.factories import UserFactory

# The site middleware queries the DB on every request.
pytestmark = pytest.mark.django_db

# A realistic SigV4 querystring: the view must pass it through byte-identical.
SIGNED_QUERY = (
    "X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=SCWXXX%2F20260907%2Ffr-par%2Fs3%2Faws4_request"
    "&X-Amz-Date=20260907T120000Z&X-Amz-Expires=3600"
    "&X-Amz-SignedHeaders=host&X-Amz-Signature=abcdef1234567890"
)


class TestPublicFileDownloadView:
    """The /fichiers/ view serves public documents through nginx."""

    def make_hosted_file(self, filename="test-guide.pdf"):
        user = UserFactory()
        hosted_file = HostedFile.objects.create(
            name="Test guide",
            file=f"documents/{filename}",
            uploaded_by=user,
        )
        hosted_file.file.storage.save(hosted_file.file.name, ContentFile(b"%PDF test"))
        return hosted_file

    def test_existing_file_returns_200(self, client):
        hosted_file = self.make_hosted_file()
        url = reverse(
            "public_file_download", kwargs={"file_path": hosted_file.file.name}
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_nonexistent_file_returns_404(self, client):
        url = reverse(
            "public_file_download", kwargs={"file_path": "documents/ghost.pdf"}
        )
        response = client.get(url)
        assert response.status_code == 404

    def test_no_login_required(self, client):
        """Public documents are accessible without authentication."""
        hosted_file = self.make_hosted_file()
        url = reverse(
            "public_file_download", kwargs={"file_path": hosted_file.file.name}
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_accented_filename(self, client):
        hosted_file = self.make_hosted_file("formulaire-simplifié.pdf")
        url = reverse(
            "public_file_download", kwargs={"file_path": hosted_file.file.name}
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_nginx_mode_pins_x_accel_header(self, client, settings):
        settings.SERVE_FILES_LOCALLY = False
        hosted_file = self.make_hosted_file()
        url = reverse(
            "public_file_download", kwargs={"file_path": hosted_file.file.name}
        )
        response = client.get(url)
        assert (
            response["X-Accel-Redirect"]
            == "/internal-s3-public/documents/test-guide.pdf"
        )
        assert response["Content-Type"] == ""

    def test_nginx_mode_x_accel_is_ascii_for_accented_filename(self, client, settings):
        settings.SERVE_FILES_LOCALLY = False
        hosted_file = self.make_hosted_file("formulaire-simplifié.pdf")
        url = reverse(
            "public_file_download", kwargs={"file_path": hosted_file.file.name}
        )
        response = client.get(url)
        assert response["X-Accel-Redirect"] == (
            "/internal-s3-public/documents/formulaire-simplifi%C3%A9.pdf"
        )


class TestPrivateFileDownloadViewLocal:
    """The /fichiers-prives/ view serves from MEDIA_ROOT in local mode."""

    def create_file_on_disk(self, settings, relative_path):
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"%PDF private test content")
        return relative_path

    def get_url(self, file_path):
        return reverse("private_file_download", kwargs={"file_path": file_path})

    def test_serves_media_file(self, client, settings):
        path = self.create_file_on_disk(settings, "media/evaluations/test.pdf")
        response = client.get(self.get_url(path))
        assert response.status_code == 200

    def test_serves_upload_file(self, client, settings):
        path = self.create_file_on_disk(settings, "upload/requests/REF123/abc.pdf")
        response = client.get(self.get_url(path))
        assert response.status_code == 200

    def test_missing_file_returns_404(self, client):
        response = client.get(self.get_url("media/evaluations/ghost.pdf"))
        assert response.status_code == 404

    def test_no_login_required(self, client, settings):
        """Authorization is page-level: the URL's signature is the credential.

        Anonymous access is by design (petitioner uploads, public map
        downloads) — adding a login requirement here would be a regression.
        """
        path = self.create_file_on_disk(settings, "media/evaluations/test.pdf")
        response = client.get(self.get_url(path))
        assert response.status_code == 200

    def test_path_traversal_returns_404(self, client):
        response = client.get("/fichiers-prives/../../etc/passwd")
        assert response.status_code == 404


class TestPrivateFileDownloadViewNginx:
    """In nginx mode, the view rebuilds the presigned S3 URL byte-identically."""

    BUCKET = "envergo-prod-private"

    @pytest.fixture(autouse=True)
    def nginx_mode(self, settings):
        settings.SERVE_FILES_LOCALLY = False
        settings.AWS_PRIVATE_BUCKET_NAME = self.BUCKET

    def test_x_accel_header_exact(self, client):
        response = client.get(
            f"/fichiers-prives/media/evaluations/test.pdf?{SIGNED_QUERY}"
        )
        assert response.status_code == 200
        assert response["X-Accel-Redirect"] == (
            f"/internal-s3-private/{self.BUCKET}/media/evaluations/test.pdf"
            f"?{SIGNED_QUERY}"
        )
        assert response["Content-Type"] == ""

    @pytest.mark.parametrize(
        "encoded_key",
        [
            # Accents: utf-8 percent-encoding must survive the decode/re-encode.
            "media/pi%C3%A8ce.pdf",
            # Space: must come back as %20, never '+'.
            "media/mon%20fichier.pdf",
            # Plus: must stay %2B, never a literal '+' nor double-encoded.
            "media/a%2Bb.pdf",
            # Percent: must stay %25.
            "media/100%25.pdf",
            # Unreserved characters must stay unencoded ('~' included).
            "media/a~b_c-d.pdf",
            # Sub-delims SigV4 encodes: apostrophe and parentheses.
            "media/l%27arr%C3%AAt%C3%A9%20%281%29.pdf",
            # Question mark: %3F must not be confused with the query separator.
            "media/rapport%3Ffinal.pdf",
        ],
    )
    def test_key_encoding_roundtrip(self, client, encoded_key):
        response = client.get(f"/fichiers-prives/{encoded_key}?{SIGNED_QUERY}")
        assert response["X-Accel-Redirect"] == (
            f"/internal-s3-private/{self.BUCKET}/{encoded_key}?{SIGNED_QUERY}"
        )

    def test_upload_prefix_exact(self, client):
        response = client.get(
            f"/fichiers-prives/upload/requests/REF/abc.pdf?{SIGNED_QUERY}"
        )
        assert response["X-Accel-Redirect"] == (
            f"/internal-s3-private/{self.BUCKET}/upload/requests/REF/abc.pdf"
            f"?{SIGNED_QUERY}"
        )

    def test_no_query_string_appends_no_question_mark(self, client):
        response = client.get("/fichiers-prives/media/evaluations/test.pdf")
        assert response["X-Accel-Redirect"] == (
            f"/internal-s3-private/{self.BUCKET}/media/evaluations/test.pdf"
        )

    def test_no_header_names_s3_host_or_bucket_publicly(self, client):
        # The bucket may only ride X-Accel-Redirect, which nginx consumes.
        response = client.get(
            f"/fichiers-prives/media/evaluations/test.pdf?{SIGNED_QUERY}"
        )
        for header, value in response.items():
            if header == "X-Accel-Redirect":
                continue
            assert "scw.cloud" not in value
            assert self.BUCKET not in value
