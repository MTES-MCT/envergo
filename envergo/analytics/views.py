from urllib.parse import parse_qs, urlencode, urlparse

from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.generic import FormView, RedirectView

from envergo.analytics.forms import FeedbackForm
from envergo.analytics.utils import log_event, set_visitor_id_cookie
from envergo.geodata.utils import get_address_from_coords
from envergo.utils.mattermost import notify


class DisableVisitorCookie(RedirectView):
    """Disable the `unique visitor id cookie` and redirect to legal mentions."""

    pattern_name = "legal_mentions"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        set_visitor_id_cookie(response, "")
        return response


class FeedbackSubmit(SuccessMessageMixin, FormView):
    form_class = FeedbackForm
    success_message = "Merci de votre retour ! Nous y répondrons dans les 24h."

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse("moulinette_home"))

    def form_valid(self, form):
        """Send the feedback as a Mattermost notification."""

        data = form.cleaned_data
        feedback_origin = self.request.META["HTTP_REFERER"]
        parsed = parse_qs(feedback_origin)
        address = get_address_from_coords(parsed["lng"][0], parsed["lat"][0])
        message_body = render_to_string(
            "analytics/feedback_mattermost_notification.txt",
            context={
                "message": data["message"],
                "address": address,
                "contact": data["contact"],
                "origin_url": feedback_origin,
            },
        )
        notify(message_body)
        log_event("feedback", "soumission", self.request)
        return super().form_valid(form)

    def get_success_url(self, *args, **kwargs):
        """Redirect form to the previous page.

        We also add a `feedback` GET parameter to prevent displaying the
        feedback form again.
        """

        # Is there a better way add a single parameter to an url?
        # Because otherwise, I'm disappointed in you Python.
        referer = self.request.META["HTTP_REFERER"]
        parsed = urlparse(referer)
        query = parse_qs(parsed.query)
        query["feedback"] = ["true"]

        # I feel weird using what looks like a private method but it's
        # mentioned in the documentation, so…
        # see https://docs.python.org/3/library/urllib.parse.html
        parsed = parsed._replace(query=urlencode(query, doseq=True))
        return parsed.geturl()
