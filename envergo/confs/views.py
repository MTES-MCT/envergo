from urllib.parse import quote

from botocore.utils import percent_encode
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.static import serve

from envergo.confs.models import HostedFile

# The nginx `internal` locations (nginx.conf.erb) that X-Accel-Redirect
# targets: nginx fetches from S3, the S3 url never reaches the client.
INTERNAL_S3_PUBLIC_PREFIX = "/internal-s3-public"
INTERNAL_S3_PRIVATE_PREFIX = "/internal-s3-private"


def reencode_s3_key(path):
    """Restore the percent-encoding a presigned S3 url carries for this path.

    Django decodes the url path while routing, but S3 signed the encoded
    form: the rebuilt url must match it byte for byte, so this mirrors
    botocore's own key encoding.
    """
    return percent_encode(path, safe="/~")


def serve_local_file(request, file_path):
    """Serve a file straight from MEDIA_ROOT (local and test environments)."""
    try:
        return serve(request, file_path, settings.MEDIA_ROOT)
    except SuspiciousFileOperation:
        # Path traversal attempt ("../" segments).
        raise Http404


def x_accel_response(redirect_uri):
    """An empty response handing the download over to nginx.

    Content-Type is blanked so nginx applies the upstream's.
    """
    response = HttpResponse()
    response["X-Accel-Redirect"] = redirect_uri
    response["Content-Type"] = ""
    return response


class PublicFileDownloadView(View):
    """Serve a public hosted document (HostedFile).

    Delegates to nginx via X-Accel-Redirect.
    """

    def get(self, request, file_path):
        hosted_file = get_object_or_404(HostedFile, file=file_path)

        if settings.SERVE_FILES_LOCALLY:
            return serve_local_file(request, hosted_file.file.name)

        # Percent-encode: headers are latin-1, non-ascii names would corrupt the key.
        return x_accel_response(quote(f"{INTERNAL_S3_PUBLIC_PREFIX}/{file_path}"))


class PrivateFileDownloadView(View):
    """Proxy a presigned private-S3 download through nginx.

    All authentication checks are fully delegated to the S3 server.
    """

    def get(self, request, file_path):
        if settings.SERVE_FILES_LOCALLY:
            return serve_local_file(request, file_path)

        key = reencode_s3_key(file_path)
        redirect_uri = (
            f"{INTERNAL_S3_PRIVATE_PREFIX}/{settings.AWS_PRIVATE_BUCKET_NAME}/{key}"
        )
        # Kept raw: the querystring holds the signature.
        query_string = request.META.get("QUERY_STRING", "")
        if query_string:
            redirect_uri = f"{redirect_uri}?{query_string}"

        # Never quote() this value: '%25' escapes would break the signature.
        return x_accel_response(redirect_uri)
