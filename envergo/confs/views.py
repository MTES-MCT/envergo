from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.static import serve

from envergo.confs.models import HostedFile

# Matches the `internal` location defined in nginx.conf.erb that proxies
# to the public S3 bucket. Nginx intercepts this header and serves the
# file directly — the path never reaches the client.
INTERNAL_S3_PUBLIC_PREFIX = "/internal-s3-public"


class HostedFileDownloadView(View):
    """Serve a public hosted file.

    In production, delegates to nginx via X-Accel-Redirect for efficient
    serving. In development, serves from the local media root.
    """

    def get(self, request, file_path):
        hosted_file = get_object_or_404(HostedFile, file=file_path)

        if settings.DEBUG:
            return serve(request, hosted_file.file.name, settings.MEDIA_ROOT)

        response = HttpResponse()
        response["X-Accel-Redirect"] = f"{INTERNAL_S3_PUBLIC_PREFIX}/{file_path}"
        response["Content-Type"] = ""
        return response
