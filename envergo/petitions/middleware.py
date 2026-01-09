from datetime import timedelta

from django.conf import settings
from django.contrib import messages

from envergo.petitions.models import InvitationToken


class HandleInvitationTokenMiddleware:
    """Handle invitation tokens.

    Store invitations token in session if the user is not logged in.
    Process the invitation if it is valid.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        url_token = request.GET.get(settings.INVITATION_TOKEN_COOKIE_NAME)
        cookie_token = request.COOKIES.get(settings.INVITATION_TOKEN_COOKIE_NAME)
        delete_cookie_token = False

        # User is authenticated. We look for invitation tokens in url
        # or in session data.
        if request.user.is_authenticated:
            if url_token:
                self.process_token(request, url_token)

            if cookie_token:
                self.process_token(request, cookie_token)
                delete_cookie_token = True

        # We process the invitation to prevent a 403 on the requested url
        response = self.get_response(request)

        # Clear the cookie token if it exists
        if delete_cookie_token:
            self.clear_token(response)

        # User is not authenticated and an invitation token is found in
        # the url. We just store the token in session to be used later.
        if url_token and not request.user.is_authenticated:
            self.store_token(request, response, url_token)

        return response

    def store_token(self, request, response, token):
        """Store the given token in session.

        Note : le cookie respecte les contraintes imposées par la CNIL
        peut donc être exempté de consentement.

        > En ce qui concerne les traceurs non soumis au consentement,
        on peut évoquer […] les traceurs destinés à l’authentification auprès d’un
        service…

        https://www.cnil.fr/fr/cookies-et-autres-traceurs/que-dit-la-loi

        """

        lifetime = timedelta(30 * 13)  # 13 months
        response.set_cookie(
            settings.INVITATION_TOKEN_COOKIE_NAME,
            token,
            max_age=lifetime.total_seconds(),
            domain=settings.SESSION_COOKIE_DOMAIN,
            path=settings.SESSION_COOKIE_PATH,
            secure=settings.SESSION_COOKIE_SECURE or None,
            httponly=True,
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )

        messages.info(
            request,
            """
            Pour accéder au dossier en tant qu’invité,
            connectez-vous ou créez un compte sur le Guichet Unique de la Haie.
            """,
        )

    def process_token(self, request, token):
        """Accepts the invitation."""

        invitation = InvitationToken.objects.filter(token=token).first()

        if invitation:
            if invitation.is_valid(request.user):
                invitation.user = request.user
                invitation.save()

                messages.info(request, "Un dossier a été rattaché à votre compte.")
            else:
                messages.warning(
                    request,
                    """
                    Le lien d'invitation utilisé n'est plus valide.
                    Il a peut-être déjà été utilisé ou a expiré.
                    Veuillez contacter la personne qui vous l'a transmis pour obtenir
                    un nouveau lien.""",
                )

    def clear_token(self, response):
        response.delete_cookie(settings.INVITATION_TOKEN_COOKIE_NAME)
