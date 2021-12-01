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
