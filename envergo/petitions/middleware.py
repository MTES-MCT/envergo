from datetime import timedelta

from django.conf import settings

from envergo.petitions.models import InvitationToken


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


class ActivateInvitationMiddleware:
    """Activate invitation tokens in session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        token = request.COOKIES.get(settings.INVITATION_TOKEN_COOKIE_NAME)
        if token and request.user.is_authenticated:
            invitation = InvitationToken.objects.filter(token=token).first()
            if invitation and invitation.is_valid(request.user):
                invitation.user = request.user
                invitation.save()
                response.delete_cookie(settings.INVITATION_TOKEN_COOKIE_NAME)

        return response
