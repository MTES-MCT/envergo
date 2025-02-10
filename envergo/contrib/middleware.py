import io
import logging
import sys

import objgraph
from django.conf import settings
from django.contrib.sites.models import Site

logger = logging.getLogger(__name__)


class SetUrlConfBasedOnSite:
    """Depending on the served site, the urlconf will vary.
    We are not overriding settings.ROOT_URLCONF because settings should not be changed at runtime,
    it implies erratic behavior.
    By default, we use the EnvErgo Amenagement urlconf.
    If the site is the Haie site, we use the Envergo Haie urlconf.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.urlconf = "config.urls_amenagement"
        site = Site.objects.get_current(request)
        request.site = site
        request.base_template = "amenagement/base.html"
        if site.domain == settings.ENVERGO_HAIE_DOMAIN:
            request.urlconf = "config.urls_haie"
            request.base_template = "haie/base.html"

        response = self.get_response(request)

        return response


class MemoryUsageMiddleware:
    """Track memory usage of each request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith(".js"):
            return self.get_response(request)

        leaking_objects = objgraph.get_leaking_objects()
        leaking_object_size = sum(sys.getsizeof(obj) for obj in leaking_objects)
        leaking_object_before_request_size_kib = leaking_object_size / 1024
        # self.log_memory_usage(request, "Before request")  # Log object growth before request

        response = self.get_response(request)

        leaking_objects = objgraph.get_leaking_objects()
        leaking_object_size = sum(sys.getsizeof(obj) for obj in leaking_objects)
        leaking_object_after_request_size_kib = leaking_object_size / 1024
        self.log_memory_usage(
            request,
            f"After request\nSize of leaking objects: "
            f"{leaking_object_after_request_size_kib - leaking_object_before_request_size_kib:.2f} KiB",
        )
        return response

    def log_memory_usage(self, request, message=None):
        buffer = io.StringIO()
        objgraph.show_growth(limit=100, file=buffer)
        route_info = f"Route: {request.path}\n" if request else ""
        logger.info(
            f"{f'{message}\n' if message else ''}{route_info}{buffer.getvalue()}"
        )
