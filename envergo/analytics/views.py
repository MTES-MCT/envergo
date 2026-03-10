import json
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, RedirectView, View
from django.views.generic.edit import BaseFormView
from django_ratelimit.decorators import ratelimit

from envergo.analytics.forms import EventForm, FeedbackForm, FeedbackRespondForm
from envergo.analytics.models import CSPReport
from envergo.analytics.utils import get_matomo_tags, log_event, set_visitor_id_cookie
from envergo.geodata.utils import get_address_from_coords
from envergo.utils.mattermost import notify
from envergo.utils.tools import get_site_literal


class DisableVisitorCookie(RedirectView):
    """Disable the `unique visitor id cookie` and redirect to legal mentions."""

    pattern_name = "legal_mentions"

    def get_redirect_url(self, *args, **kwargs):
        """Redirect to the previous page.

        If somehow the referer is missing, we fallback to the default redirect url.
        """
        referer = self.request.META.get("HTTP_REFERER")
        redirect_url = super().get_redirect_url(*args, **kwargs)
        return referer or redirect_url

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
    """Sends a Mattermost notification when the feedback form is clicked.

    Note: this view is called via ajax when the feedback form modal is opened.

    """

    form_class = FeedbackRespondForm

    def form_valid(self, form):
        address = self.parse_address()
        feedback_origin = self.request.META.get("HTTP_REFERER")
        feedback = form.cleaned_data["feedback"]
        metadata = form.cleaned_data.get("moulinette_data", {})
        metadata["feedback"] = feedback
        mtm_keys = get_matomo_tags(self.request)
        metadata.update(mtm_keys)

        message_body = render_to_string(
            "analytics/mattermost_feedback_respond.txt",
            context={
                "address": address,
                "feedback": feedback,
                "origin_url": feedback_origin,
            },
        )
        notify(message_body, get_site_literal(self.request.site))
        log_event("FeedbackDialog", "Respond", self.request, **metadata)
        return HttpResponse(message_body)

    def form_invalid(self, form):
        """Handle invalid requests.

        This should not happen, unless the user tampered with the ajax request.
        """
        return HttpResponseBadRequest(f"{form.errors}")


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST"), name="post")
class FeedbackSubmit(SuccessMessageMixin, ParseAddressMixin, FormView):
    """Process the feedback modal form."""

    form_class = FeedbackForm
    success_message = "Merci de votre retour."

    def get_prefix(self):
        if "useful-feedback" in self.request.POST:
            prefix = "useful"
        else:
            prefix = "useless"
        return prefix

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse("moulinette_form"))

    def form_valid(self, form):
        """Send the feedback as a Mattermost notification."""

        data = form.cleaned_data
        metadata = {}
        metadata.update(data)

        moulinette_data = form.cleaned_data.get("moulinette_data", {})
        if moulinette_data:
            metadata.update(moulinette_data)

        mtm_keys = get_matomo_tags(self.request)
        metadata.update(mtm_keys)

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
        notify(message_body, get_site_literal(self.request.site))
        log_event("FeedbackDialog", "FormSubmit", self.request, **metadata)
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


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST"), name="post")
class Events(FormView):
    form_class = EventForm
    http_method_names = ["post"]

    def form_valid(self, form):
        data = form.cleaned_data
        log_event(
            data["category"],
            data["action"],
            self.request,
            **data["metadata"],
        )
        return JsonResponse({"status": "ok"})

    def form_invalid(self, form):
        return JsonResponse({"status": "error", "errors": form.errors})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="50/m", method="POST"), name="post")
class CSPReportView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        content = json.loads(request.body)
        visitor_id = request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")
        CSPReport.objects.create(
            content=content, site=request.site, session_key=visitor_id
        )

        return HttpResponse()
