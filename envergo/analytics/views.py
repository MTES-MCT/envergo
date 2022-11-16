from urllib.parse import parse_qs, urlencode, urlparse

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import FormView, RedirectView
from django.views.generic.edit import BaseFormView
from ratelimit.decorators import ratelimit

from envergo.analytics.forms import FeedbackForm, FeedbackRespondForm
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


class ParseAddressMixin:
    """Easily fetch an address from coordinates in the referer url."""

    def parse_address(self):
        referer_url = self.request.META.get("HTTP_REFERER")
        parsed = parse_qs(referer_url)
        try:
            address = get_address_from_coords(parsed["lng"][0], parsed["lat"][0])
        except KeyError:
            address = "NA"
        return address


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST"), name="post")
class FeedbackRespond(ParseAddressMixin, BaseFormView):
    """Sends a Mattermost notification when the feedback form is clicked."""

    form_class = FeedbackRespondForm

    def form_valid(self, form):
        address = self.parse_address()
        feedback_origin = self.request.META.get("HTTP_REFERER")

        message_body = render_to_string(
            "analytics/mattermost_feedback_respond.txt",
            context={
                "address": address,
                "feedback": form.cleaned_data["feedback"],
                "origin_url": feedback_origin,
            },
        )
        notify(message_body)
        log_event("feedback", "réponse", self.request)
        return HttpResponse(message_body)

    def form_invalid(self, form):
        """Handle invalid requests.

        This should not happen, unless the user tampered with the ajax request.
        """
        return HttpResponseBadRequest(f"{form.errors}")


class FeedbackSubmit(SuccessMessageMixin, ParseAddressMixin, FormView):
    form_class = FeedbackForm
    success_message = "Merci de votre retour."

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse("moulinette_home"))

    def form_valid(self, form):
        """Send the feedback as a Mattermost notification."""

        data = form.cleaned_data
        feedback_origin = self.request.META.get("HTTP_REFERER")
        address = self.parse_address()
        message_body = render_to_string(
            "analytics/mattermost_feedback_submit.txt",
            context={
                "message": data["message"],
                "address": address,
                "contact": data["contact"],
                "feedback": data["feedback"],
                "profile": form.get_you_are_display(),
                "origin_url": feedback_origin,
            },
        )
        notify(message_body)
        log_event("feedback", "soumission", self.request)
        return super().form_valid(form)

    def form_invalid(self, form):
        # This should not happen, but just in case, let's not display
        # an ugly 500 error page to the user.
        messages.error(
            self.request,
            "Une erreur technique nous a empêché de réceptionner votre retour. "
            "Veuillez nous excuser pour ce désagrément.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self, *args, **kwargs):
        """Redirect form to the previous page.

        We also add a `feedback` GET parameter to prevent displaying the
        feedback form again.
        """

        # We want to redirect to the url where the feedback comes from
        # If for some reason, the referer META is missing, let's prevent
        # an error and redirect to home instead.
        referer = self.request.META.get("HTTP_REFERER")
        home_url = reverse("home")
        redirect_url = referer or home_url

        # Is there a better way add a single parameter to an url?
        # Because otherwise, I'm disappointed in you Python.
        parsed = urlparse(redirect_url)
        query = parse_qs(parsed.query)
        query["feedback"] = ["true"]

        # I feel weird using what looks like a private method but it's
        # mentioned in the documentation, so…
        # see https://docs.python.org/3/library/urllib.parse.html
        parsed = parsed._replace(query=urlencode(query, doseq=True))
        return parsed.geturl()
