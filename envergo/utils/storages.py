from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticRootS3Boto3Storage(S3Boto3Storage):
    location = "static"
    default_acl = "public-read"


class MediaRootS3Boto3Storage(S3Boto3Storage):
    location = "media"
    file_overwrite = False


class UploadS3Boto3Storage(S3Boto3Storage):
    location = "upload"
    bucket_name = settings.AWS_UPLOAD_BUCKET_NAME


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
