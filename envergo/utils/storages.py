from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.encoding import filepath_to_uri
from storages.backends.s3boto3 import S3Boto3Storage

# All S3 urls are proxied through the application.
# Must match config/urls.py and the nginx internal locations.
PUBLIC_FILES_URL_PREFIX = "/fichiers"
PRIVATE_FILES_URL_PREFIX = "/fichiers-prives"


class ProxiedPrivateS3Mixin:
    """Common class for all private file storages.

    Files are hosted on S3, but S3 urls must *never* leak, so we proxy them
    through the application.

    Private S3 buckets use signed urls. Those acl parameters are transfered as is.
    """

    def s3_url(self, name, parameters=None, expire=None, http_method=None):
        """The raw presigned S3 URL.

        For server-side consumers only (tasks fetching file content, webhooks
        to third parties). Must never be rendered into a page.
        """
        return super().url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )

    def url(self, name, parameters=None, expire=None, http_method=None):
        """A browser-safe proxy URL carrying the presigned querystring."""
        signed_url = self.s3_url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )

        path_style_prefix = f"{self.endpoint_url}/{self.bucket_name}/"
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

    bucket_name = settings.AWS_PRIVATE_BUCKET_NAME
    location = "media"
    default_acl = "private"
    file_overwrite = False
    querystring_auth = True
    querystring_expire = 3600


class PrivateUploadStorage(ProxiedPrivateS3Mixin, S3Boto3Storage):
    """Petitioner-submitted files (RequestFile)."""

    bucket_name = settings.AWS_PRIVATE_BUCKET_NAME
    location = "upload"
    default_acl = "private"
    file_overwrite = False
    querystring_auth = True
    querystring_expire = 3600


class PublicMediaStorage(S3Boto3Storage):
    """Public documents (HostedFile). Separate bucket, stable URLs."""

    bucket_name = settings.AWS_PUBLIC_BUCKET_NAME
    default_acl = "public-read"
    file_overwrite = False
    querystring_auth = False

    def s3_url(self, name, parameters=None, expire=None, http_method=None):
        """The raw S3 URL, for server-side consumers only."""
        return super().url(
            name, parameters=parameters, expire=expire, http_method=http_method
        )

    def url(self, name):
        # Route through the public download proxy so no template can leak the
        # bucket host. The route serves DB-registered HostedFile paths only.
        return f"{PUBLIC_FILES_URL_PREFIX}/{filepath_to_uri(name)}"


class LocalFileStorage(FileSystemStorage):
    """A FileSystemStorage exposing the same interface as the S3 storages."""

    def s3_url(self, name):
        return self.url(name)
