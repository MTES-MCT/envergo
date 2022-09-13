from django.views.generic import RedirectView

from config.settings.base import VISITOR_COOKIE_NAME


class DisableVisitorCookie(RedirectView):
    """Disable the `unique visitor id cookie` and redirect to legal mentions."""

    pattern_name = 'legal_mentions'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.set_cookie(VISITOR_COOKIE_NAME, '')
        return response
