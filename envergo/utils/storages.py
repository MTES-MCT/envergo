from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class PrivateMediaStorage(S3Boto3Storage):
    """Default storage for sensitive files (evaluations, petitions, maps, etc.)."""

    bucket_name = settings.AWS_PRIVATE_BUCKET_NAME
    location = "media"
    default_acl = "private"
    file_overwrite = False
    querystring_auth = True
    querystring_expire = 3600


class PrivateUploadStorage(S3Boto3Storage):
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


class TchapCryptoStoreS3Storage(S3Boto3Storage):
    """Storage for the Tchap bot's E2EE crypto store.

    Unlike the other storages above, this one holds private key material, so
    it must never inherit the project's default public-read ACL. It also
    checkpoints the same object repeatedly, so overwriting in place (rather
    than the usual "never overwrite user uploads" behavior) is the point.
    """

    location = "tchap-crypto-store"
    bucket_name = settings.AWS_UPLOAD_BUCKET_NAME
    default_acl = "private"
    file_overwrite = True
