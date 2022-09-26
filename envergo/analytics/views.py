from django.contrib.messages.views import SuccessMessageMixin
from django.template.loader import render_to_string
from django.views.generic import FormView, RedirectView

from config.settings.base import VISITOR_COOKIE_NAME
from envergo.analytics.forms import FeedbackForm
from envergo.utils.mattermost import notify


class DisableVisitorCookie(RedirectView):
    """Disable the `unique visitor id cookie` and redirect to legal mentions."""

    pattern_name = "legal_mentions"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.set_cookie(VISITOR_COOKIE_NAME, "")
        return response


class FeedbackSubmit(SuccessMessageMixin, FormView):
    form_class = FeedbackForm
    success_message = "Merci de votre retour. Nous y répondrons dans les 24h."

    def form_valid(self, form):
        """Send the feedback as a Mattermost notification."""

        data = form.cleaned_data
        feedback_origin = self.request.META["HTTP_REFERER"]
        message_body = render_to_string(
            "analytics/feedback_mattermost_notification.txt",
            context={
                "message": data["message"],
                "contact": data["contact"],
                "origin_url": feedback_origin,
            },
        )
        notify(message_body)
        return super().form_valid(form)

    def get_success_url(self, *args, **kwargs):
        """Redirect form to the previous page."""

        return self.request.META["HTTP_REFERER"]
