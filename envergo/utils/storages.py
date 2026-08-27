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
