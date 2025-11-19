from django.conf import settings
from django.shortcuts import render
from django_ratelimit import UNSAFE
from django_ratelimit.core import is_ratelimited


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
            return render(request, "429.html", status=429)

        return self.get_response(request)
