from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.encoding import filepath_to_uri
from storages.backends.s3boto3 import S3Boto3Storage

# All S3 urls are proxied through the application.
# Must match the routes in config/urls.py.
PUBLIC_FILES_URL_PREFIX = "/fichiers"
PRIVATE_FILES_URL_PREFIX = "/fichiers-prives"


def download_source(field_file):
    """Where to read a stored file from: an S3 url, or a local filesystem path."""
    url = field_file.storage.s3_url(field_file.name)
    if url.startswith("http"):
        return url
    return field_file.path


class S3UrlMixin:
    """Expose the raw S3 url alongside the browser-facing url() override."""

    def s3_url(self, name, parameters=None, expire=None, http_method=None):
        """The raw S3 URL. Server-side consumers only — never rendered into a page."""
        return super().url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )


class ProxiedPrivateS3Mixin(S3UrlMixin):
    """Mixin for all private file storages.

    Files are hosted on S3, but S3 urls must *never* leak, so we proxy them
    through the application. The presigned querystring is the access
    credential; it passes through unchanged.
    """

    bucket_name = settings.AWS_PRIVATE_BUCKET_NAME
    default_acl = "private"
    file_overwrite = False
    querystring_auth = True
    querystring_expire = 3600

    def url(self, name, parameters=None, expire=None, http_method=None):
        """A browser-safe proxy URL carrying the presigned querystring."""
        signed_url = self.s3_url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )

        endpoint = self.endpoint_url.rstrip("/")
        path_style_prefix = f"{endpoint}/{self.bucket_name}/"
        if not signed_url.startswith(path_style_prefix):
            raise ImproperlyConfigured(
                f"Presigned URL {signed_url} is not path-style on the "
                "configured endpoint; check AWS_S3_ADDRESSING_STYLE and "
                "AWS_S3_ENDPOINT_URL."
            )

        # Never re-encode the signed path: it must pass through byte-identical.
        signed_path = signed_url.removeprefix(path_style_prefix)
        return f"{PRIVATE_FILES_URL_PREFIX}/{signed_path}"


class PrivateMediaStorage(ProxiedPrivateS3Mixin, S3Boto3Storage):
    """Default storage for sensitive files (evaluations, petitions, maps, etc.)."""

    location = "media"


class PrivateUploadStorage(ProxiedPrivateS3Mixin, S3Boto3Storage):
    """Petitioner-submitted files (RequestFile)."""

    location = "upload"


class PublicMediaStorage(S3UrlMixin, S3Boto3Storage):
    """Public documents (HostedFile). Separate bucket, stable URLs."""

    bucket_name = settings.AWS_PUBLIC_BUCKET_NAME
    default_acl = "public-read"
    file_overwrite = False
    querystring_auth = False

    def url(self, name, parameters=None, expire=None, http_method=None):
        # Route through the public download proxy so no template can leak the
        # bucket host. The route serves DB-registered HostedFile paths only.
        return f"{PUBLIC_FILES_URL_PREFIX}/{filepath_to_uri(name)}"


class LocalFileStorage(FileSystemStorage):
    """A FileSystemStorage exposing the same interface as the S3 storages."""

    def s3_url(self, name, parameters=None, expire=None, http_method=None):
        return self.url(name)
