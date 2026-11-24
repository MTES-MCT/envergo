from django import http
from django.conf import settings
from django.db import transaction
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from health_check.views import HealthCheckView


class EnvergoHealthCheckView(HealthCheckView):
    auth_token: str | None = None
    """Secret bearer token that authenticates a request and skips the cache."""

    @method_decorator(transaction.non_atomic_requests)
    async def dispatch(self, request, *args, **kwargs):
        if self.is_authorized(request):
            response = await super().dispatch(request, *args, **kwargs)
            patch_vary_headers(response, ["Accept"])
            if self.get_auth_token():
                patch_vary_headers(response, ["Authorization"])
            response = self.patch_cache_headers(request, response)
        else:
            response = http.HttpResponseForbidden(
                "Authentication failed", content_type="text/plain; charset=utf-8"
            )
            patch_vary_headers(response, ["Authorization"])
        return response

    def is_authorized(self, request) -> bool:
        """To access the view: bear the auth token, or be logged as staff user"""
        auth_token = self.get_auth_token()

        if auth_token:
            scheme, _, token = request.headers.get("Authorization", "").partition(" ")
            return (
                scheme.lower() == "bearer" and constant_time_compare(token, auth_token)
            ) or (request.user.is_authenticated and request.user.is_staff)
        return False

    def get_auth_token(self) -> str | None:
        """Return the bearer token from the view or the settings."""
        return self.auth_token or getattr(settings, "HEALTH_CHECK_AUTH_TOKEN", None)

    def patch_cache_headers(
        self, request: http.HttpRequest, response: http.HttpResponseBase
    ) -> http.HttpResponseBase:
        patch_cache_control(response, no_store=True)
        return response
