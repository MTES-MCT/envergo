from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import FormView, RedirectView

from config.settings.base import VISITOR_COOKIE_NAME
from envergo.analytics.forms import FeedbackForm


class DisableVisitorCookie(RedirectView):
    """Disable the `unique visitor id cookie` and redirect to legal mentions."""

    pattern_name = "legal_mentions"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.set_cookie(VISITOR_COOKIE_NAME, "")
        return response


class FeedbackSubmit(SuccessMessageMixin, FormView):
    form_class = FeedbackForm
    success_message = 'Merci de votre retour. Nous y répondrons dans les 24h.'

    def get_success_url(self, *args, **kwargs):
        """Redirect form to the previous page."""

        return self.request.META['HTTP_REFERER']
