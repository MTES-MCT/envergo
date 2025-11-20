import logging

from django.conf import settings
from django.shortcuts import render
from django.utils.translation import gettext as _
from django_ratelimit import UNSAFE
from django_ratelimit.core import _get_ip, is_ratelimited

logger = logging.getLogger(__name__)


class RateLimitingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Global rate limit on POST, PUT, PATCH and DELETE: 100 req/min per IP
        limited = is_ratelimited(
            request,
            group="global",
            key="ip",
            rate=settings.RATELIMIT_RATE,
            method=UNSAFE,
            increment=True,
        )

        if limited:
            logger.warning(
                "Global rate limit exceeded for an unsafe request (POST/PUT/PATCH/DELETE)",
                extra={
                    "ip": _get_ip(request),
                    "path": request.path,
                    "visitor_id": request.COOKIES.get(settings.VISITOR_COOKIE_NAME, ""),
                },
            )
            return render(request, "429.html", status=429)

        # Rate limit on GET requests for moulinette routes
        if request.method == "GET" and request.path.startswith(f'/{_("moulinette/")}'):
            limited = is_ratelimited(
                request,
                group="limited_get",
                key="ip",
                rate=settings.RATELIMIT_RATE,
                method=["GET"],
                increment=True,
            )
            if limited:
                logger.warning(
                    "Rate limit exceeded for a GET request",
                    extra={
                        "ip": _get_ip(request),
                        "path": request.path,
                        "visitor_id": request.COOKIES.get(
                            settings.VISITOR_COOKIE_NAME, ""
                        ),
                    },
                )
                return render(request, "429.html", status=429)

        return self.get_response(request)
