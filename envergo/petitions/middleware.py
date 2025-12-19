from datetime import timedelta

from django.conf import settings


class StoreInvitationToken:
    """Store invitation tokens in session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        new_token = request.GET.get("invitation_token")
        response = self.get_response(request)
        if new_token:
            lifetime = timedelta(30 * 13)  # 13 months
            response.set_cookie(
                settings.INVITATION_TOKEN_COOKIE_NAME,
                new_token,
                max_age=lifetime.total_seconds(),
                domain=settings.SESSION_COOKIE_DOMAIN,
                path=settings.SESSION_COOKIE_PATH,
                secure=settings.SESSION_COOKIE_SECURE or None,
                httponly=True,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

        return response
