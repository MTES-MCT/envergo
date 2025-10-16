import json
from urllib.parse import urlencode

from django.conf import settings
from django.forms.widgets import CheckboxInput
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import FormView

from envergo.analytics.forms import FeedbackFormUseful, FeedbackFormUseless
from envergo.analytics.utils import (
    extract_matomo_url_from_request,
    get_matomo_tags,
    is_request_from_a_bot,
    log_event,
    update_url_with_matomo_params,
)
from envergo.evaluations.models import TagStyleEnum
from envergo.geodata.utils import get_address_from_coords
from envergo.hedges.services import PlantationEvaluator
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import get_moulinette_class_from_site
from envergo.moulinette.utils import compute_surfaces
from envergo.utils.urls import copy_qs, remove_from_qs, update_qs


class MoulinetteMixin:
    """Display the moulinette form and results."""

    def setup(self, request, *args, **kwargs):
        """Add a moulinette object to the view.

        This method is called even before `dispatch` in django's class-based view
        workflow.

        This guarantees that a "moulinette" property is always available.
        """
        super().setup(request, *args, **kwargs)
        MoulinetteClass = get_moulinette_class_from_site(request.site)
        self.moulinette = MoulinetteClass(self.get_form_kwargs())

    def get_form_class(self):
        FormClass = self.moulinette.get_main_form_class()
        return FormClass

    def get_form(self):
        form = self.moulinette.main_form
        return form

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
        }

        if self.request.method in ("POST", "PUT"):
            kwargs["data"] = self.get_form_data()

        return kwargs

    def get_initial(self):
        moulinette_data = self.request.GET.dict()
        if moulinette_data:
            surfaces = compute_surfaces(moulinette_data)
            moulinette_data.update(surfaces)

        return moulinette_data

    def get_form_data(self):
        """Get the data to pass to the moulinette forms.

        Mainly the POSTed data, but we also compute the surface related fields.
        """

        moulinette_data = self.request.POST.dict()
        if moulinette_data:
            surfaces = compute_surfaces(moulinette_data)
            moulinette_data.update(surfaces)

        return moulinette_data

    def clean_request_get_parameters(self):
        """Remove parameters that don't belong to the moulinette form.

        Mainly, we want to ignore parameters set by different analytics systems
        because they are messing with the moulinette form processing.
        """
        ignore_prefixes = ["mtm_", "utm_", "pk_", "piwik_", "matomo_"]
        GET = self.request.GET.copy().dict()
        keys = GET.keys()
        for key in list(keys):
            for prefix in ignore_prefixes:
                if key.startswith(prefix):
                    GET.pop(key)
        return GET

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["moulinette"] = self.moulinette
        context.update(self.moulinette.catalog)

        if self.moulinette.is_evaluated():

            context["has_errors"] = (
                self.request.method == "POST" and not self.moulinette.is_valid()
            )
            context["additional_forms"] = self.moulinette.additional_forms
            context["additional_fields"] = self.moulinette.additional_fields

            # We need to display a different form style when the "additional forms"
            # first appears, but the way this feature is designed, said forms
            # are always "bound" when they appear. So we have to check for the
            # presence of field keys in the GET parameters.
            context["additional_forms_bound"] = (
                self.moulinette.are_additional_forms_bound()
            )

            moulinette_data = self.moulinette.summary()
            context["moulinette_summary"] = json.dumps(moulinette_data)
            context["feedback_form_useful"] = FeedbackFormUseful(
                prefix="useful",
                initial={"feedback": "Oui", "moulinette_data": moulinette_data},
            )
            context["feedback_form_useless"] = FeedbackFormUseless(
                prefix="useless",
                initial={"feedback": "Non", "moulinette_data": moulinette_data},
            )

        # Should we center the map on the given coordinates, or zoom out on
        # the entire country?
        if "lng" in context and "lat" in context:
            lng, lat = context["lng"], context["lat"]
            context["display_marker"] = True
            context["center_map"] = [lng, lat]
            context["default_zoom"] = 16
        else:
            # By default, show all metropolitan france in map
            context["display_marker"] = False
            context["center_map"] = [1.7000, 47.000]
            context["default_zoom"] = 5

        context["is_map_static"] = False
        context["visitor_id"] = self.request.COOKIES.get(
            settings.VISITOR_COOKIE_NAME, ""
        )

        context["optional_forms"] = self.moulinette.optional_forms
        context["triage_form"] = self.moulinette.triage_form

        context = {**context, **self.moulinette.get_extra_context(self.request)}

        return context

    def get_results_params(self):
        """Return the list of parameters that must go in the url."""

        # We might have some values in the url parameters
        # and some values sent with the form submission.
        # In the moulinette result view, all the moulinette values
        # are passed by the url.
        # To build a valid moulinette result url, we need to take the existing url parameters
        # and update them with all the POST'ed moulinette form data.

        # There is an hedge case though with checkbox inputs.
        # When a checkbox is left empty, browsers don't send a "false" value, they
        # send no value at all, meaning an existing value in the url will NOT
        # be overriden.
        url_data = self.request.GET.copy().dict()
        data = {}
        fields = self.moulinette.get_prefixed_fields()
        for k, v in url_data.items():
            field = fields.get(k)
            if field and isinstance(field.widget, CheckboxInput):
                continue
            data[k] = v

        cleaned_data = self.moulinette.cleaned_data
        data.update(cleaned_data)
        return data

    def get_form_url(self):
        """Return the moulinette form url, with the correct url params."""

        data = self.get_results_params()
        params = urlencode(data)
        url = reverse("moulinette_form")

        url_with_params = f"{url}?{params}"
        return url_with_params

    def get_result_url(self):
        """Generates the full url to the moulinette result page."""

        data = self.get_results_params()
        params = urlencode(data)
        url = reverse("moulinette_result")

        url_with_params = f"{url}?{params}"
        return url_with_params

    def log_moulinette_event(self, moulinette, context, **kwargs):
        export = moulinette.summary()
        export.update(kwargs)
        export["url"] = self.request.build_absolute_uri()

        if self.request.site.domain == settings.ENVERGO_AMENAGEMENT_DOMAIN:
            action = self.event_action_amenagement
        else:
            action = self.event_action_haie

        mtm_keys = get_matomo_tags(self.request)
        export.update(mtm_keys)

        log_event(
            self.event_category,
            action,
            self.request,
            **export,
        )


@method_decorator(xframe_options_sameorigin, name="dispatch")
class MoulinetteForm(MoulinetteMixin, FormView):

    def get_template_names(self):
        return self.moulinette.get_home_template()

    def post(self, request, *args, **kwargs):
        # If the moulinette is valid, i.e it can run the eveluation and provide
        # a result, then we redirect to the result page
        if self.moulinette.is_valid():
            return HttpResponseRedirect(self.get_result_url())

        # If the main form is valid and all the errors are missing data, it means
        # that filling the main form triggered new additional questions. We then
        # redirect to the current form with the submitted values in the url.
        elif (
            self.moulinette.main_form.is_valid()
            and not self.moulinette.are_additional_forms_bound()
        ):
            return HttpResponseRedirect(f"{self.get_form_url()}#additional-forms")

        # In other cases, it means there are errors in one of the submitted forms,
        # so we just display back the page with the validation errors
        else:
            return self.form_invalid(self.moulinette.main_form)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)

        main_form_errors = {
            field: [{"code": str(e.code), "message": str(e.message)} for e in errors]
            for field, errors in form.errors.as_data().items()
        }
        optional_forms = context["optional_forms"]
        optional_forms_errors = {
            f"{optional_form.prefix}-{field}": [
                {"code": str(e.code), "message": str(e.message)} for e in errors
            ]
            for optional_form in optional_forms
            if optional_form.is_activated() and optional_form.errors
            for field, errors in optional_form.errors.as_data().items()
        }
        log_event(
            "erreur",
            "formulaire-simu",
            self.request,
            data=form.data,
            errors=main_form_errors | optional_forms_errors,
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["matomo_custom_url"] = extract_matomo_url_from_request(self.request)

        form = context["form"]
        if form.is_bound and not form.is_valid():
            invalid_form_url = self.request.build_absolute_uri(
                reverse("moulinette_invalid_form")
            )
            context["matomo_custom_url"] = update_url_with_matomo_params(
                invalid_form_url, self.request
            )

        return context


class MoulinetteResultMixin:
    """Common code for views displaying moulinette results."""

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""

        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
            "data": self.clean_request_get_parameters(),
        }
        return kwargs

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""

        moulinette = self.moulinette
        triage_form = moulinette.triage_form
        triage_is_valid = self.moulinette.is_triage_valid()
        is_debug = bool(self.request.GET.get("debug", False))
        is_admin = self.request.user.is_staff

        # We want to display the moulinette result template, but must check all
        # previous cases where we cannot do it
        if triage_form and not triage_is_valid:
            template_name = moulinette.get_triage_result_template()
        elif is_debug:
            template_name = moulinette.get_debug_result_template()
        elif not moulinette.has_config():
            template_name = moulinette.get_result_non_disponible_template()
        elif not (moulinette.is_evaluation_available() or is_admin):
            template_name = moulinette.get_result_available_soon_template()
        elif moulinette.has_missing_data():
            # This case should not happen, because we redirect to the form view
            # earlier
            template_name = moulinette.get_home_template()
        else:
            template_name = moulinette.get_result_template()

        return [template_name]

    def get_analytics_context_data(self, context):
        """Custom context data related to analytics.

        We have to build a bunch of "fake" urls for tracking purpose.
        For example, we want the debug page to be logged as a `/simulateur/debug/`
        url in matomo, even though the real url is `/simulateur/resultat/?debug=true`.
        """
        data = {}
        moulinette = self.moulinette
        is_debug = bool(self.request.GET.get("debug", False))
        is_alternative = bool(self.request.GET.get("alternative", False))
        # Let's build custom uris for better matomo tracking
        # Depending on the moulinette result, we want to track different uris
        # as if they were distinct pages.

        # Url without any query parameters
        # We want to build "fake" urls for matomo tracking
        # For example, if the current url is /simulateur/resultat/?debug=true,
        # We want to track this as a custom url /simulateur/debug/

        # We want to log the current simulation url stripped from any query parameters
        # except for mtm_ ones
        bare_url = self.request.build_absolute_uri(self.request.path)
        debug_url = self.request.build_absolute_uri(reverse("moulinette_result_debug"))
        missing_data_url = self.request.build_absolute_uri(
            reverse("moulinette_missing_data")
        )
        out_of_scope_result_url = self.request.build_absolute_uri(
            reverse("moulinette_result_out_of_scope")
        )
        invalid_form_url = self.request.build_absolute_uri(
            reverse("moulinette_invalid_form")
        )

        data["matomo_custom_url"] = update_url_with_matomo_params(
            bare_url, self.request
        )

        if is_alternative:
            data["matomo_custom_url"] = update_qs(
                data["matomo_custom_url"], {"alternative": "true"}
            )
        elif not moulinette.is_triage_valid():
            data["matomo_custom_url"] = update_url_with_matomo_params(
                out_of_scope_result_url, self.request
            )
        elif not moulinette.is_valid():
            data["matomo_custom_url"] = update_url_with_matomo_params(
                invalid_form_url, self.request
            )
        elif context["additional_forms_bound"]:
            data["matomo_custom_url"] = update_url_with_matomo_params(
                missing_data_url, self.request
            )
        elif is_debug:
            data["matomo_custom_url"] = update_url_with_matomo_params(
                debug_url, self.request
            )

        return data

    def get_urls_context_data(self, context):
        """Custom context data related to urls.

        We need to build different urls to make linking easier.
        For example, we dislpay a "share" button that links to the current page
        with additional mtm params, a "debug" button that links to the
        debug page, etc.
        """
        data = {}
        moulinette = self.moulinette

        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(current_url, {"mtm_campaign": "share-simu"})
        share_print_url = update_qs(current_url, {"mtm_campaign": "print-simu"})
        result_url = remove_from_qs(current_url, "debug")
        debug_result_url = update_qs(current_url, {"debug": "true"})
        form_url = reverse("moulinette_form")
        form_url = copy_qs(form_url, current_url)
        edit_url = (
            form_url if moulinette.is_valid() else context.get("triage_url", None)
        )
        data["result_url"] = result_url
        data["edit_url"] = edit_url
        data["current_url"] = current_url
        data["share_btn_url"] = share_btn_url
        data["share_print_url"] = share_print_url
        data["envergo_url"] = self.request.build_absolute_uri("/")
        data["debug_url"] = debug_result_url

        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = context.get("moulinette", None)
        is_debug = bool(self.request.GET.get("debug", False))

        context["non_disponible_tag_style"] = TagStyleEnum.Grey
        context["is_admin"] = self.request.user.is_staff
        context["is_debug"] = is_debug

        if moulinette:
            context["base_result"] = moulinette.get_result_template()
        else:
            context["base_result"] = "moulinette/base_result.html"

        if moulinette and is_debug:
            debug_context_data = moulinette.get_debug_context()
            context.update(debug_context_data)

        context["display_feedback_form"] = (
            moulinette
            and moulinette.is_evaluation_available()
            and not self.request.GET.get("feedback", False)
        )

        analytics_data = self.get_analytics_context_data(context)
        context.update(analytics_data)

        urls_data = self.get_urls_context_data(context)
        context.update(urls_data)

        return context


class BaseMoulinetteResult(FormView):
    def get(self, request, *args, **kwargs):
        moulinette = self.moulinette
        triage_form = moulinette.triage_form
        redirect_url = None

        # Triage is required and triage form is invalid
        if triage_form and not triage_form.is_valid():
            redirect_url = reverse("triage")
            redirect_url = update_qs(redirect_url, request.GET)

        # Moulinette is invalid and there is no triage to do (amenagement)
        # so just redirect to the form
        elif not moulinette.is_valid() and not (triage_form and triage_form.is_valid()):
            redirect_url = reverse("moulinette_form")
            redirect_url = update_qs(redirect_url, request.GET)

        if redirect_url:
            return HttpResponseRedirect(redirect_url)

        context = self.get_context_data(**kwargs)
        res = self.render_to_response(context)

        # Logging moulinette event
        if is_request_from_a_bot(request):
            # When we detect that the request comes from a robot
            # (e.g a search engine crawler), we don't log any event to try to keep
            # some clean analytiscs
            pass
        else:
            self.log_moulinette_event(moulinette, context)

        return res

    def log_moulinette_event(self, moulinette, context):
        if moulinette.is_triage_valid():
            super().log_moulinette_event(moulinette, context)
        else:
            # TODO Why is matomo param cleanup only happens here?
            # Matomo parameters are stored in session, but some might remain in the url.
            # We need to prevent duplicate values
            params = get_matomo_tags(self.request)
            params.update(self.request.GET.dict())
            log_event(
                "simulateur",
                "soumission_autre",
                self.request,
                **params,
            )


class MoulinetteAmenagementResult(
    MoulinetteResultMixin, MoulinetteMixin, BaseMoulinetteResult
):
    event_category = "simulateur"
    event_action_amenagement = "soumission"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = context.get("moulinette", None)

        if moulinette:
            lng = moulinette.catalog.get("lng")
            lat = moulinette.catalog.get("lat")
            if lng and lat:
                address = get_address_from_coords(lng, lat)
                if address:
                    context["address"] = address
                    context["form"].data[
                        "address"
                    ] = address  # add address as a submitted data to display it in the rendered form
                else:
                    context["address_coords"] = f"{lat}, {lng}"
                    context["form"].data["address"] = f"{lat}, {lng}"

        return context


class MoulinetteHaieResult(
    MoulinetteResultMixin, MoulinetteMixin, BaseMoulinetteResult
):
    event_category = "simulateur"
    event_action_haie = "soumission_d"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = context.get("moulinette", None)

        if moulinette and "haies" in moulinette.catalog:
            hedge_data = moulinette.catalog["haies"]
            evaluator = PlantationEvaluator(moulinette, hedge_data)
            context["plantation_evaluation"] = evaluator
            context["replantation_coefficient"] = evaluator.replantation_coefficient

            plantation_url = reverse(
                "input_hedges",
                args=[moulinette.department.department, "plantation", hedge_data.id],
            )
            plantation_url = update_qs(plantation_url, self.request.GET)
            context["plantation_url"] = plantation_url

            result_p_url = reverse("moulinette_result_plantation")
            result_p_url = update_qs(result_p_url, self.request.GET)
            context["result_p_url"] = result_p_url
        return context


class MoulinetteResultPlantation(MoulinetteHaieResult):
    event_category = "simulateur"
    event_action_haie = "soumission_p"

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""

        moulinette = self.moulinette

        # Moulinette result template for plantation is not the moulinette ABC class result template
        # So we get the template name super and check specific cases

        template_name = super().get_template_names()[0]

        if moulinette.has_missing_data():  # TODO missing only hedges to plant
            template_name = moulinette.get_result_template()
        elif template_name == "haie/moulinette/result.html":
            template_name = "haie/moulinette/result_plantation.html"

        return [template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = context.get("moulinette", None)
        context["is_result_plantation"] = True

        if moulinette:
            evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
            context["plantation_evaluation"] = evaluator
            context["replantation_coefficient"] = evaluator.replantation_coefficient

            hedge_data_id = self.request.GET.get("haies")
            plantation_url = reverse(
                "input_hedges",
                args=[moulinette.department.department, "plantation", hedge_data_id],
            )
            plantation_url = update_qs(plantation_url, self.request.GET)
            context["plantation_url"] = plantation_url

        form_url = update_qs(reverse("moulinette_form"), self.request.GET)
        context["edit_url"] = form_url
        return context

    def log_moulinette_event(self, moulinette, context, **kwargs):
        kwargs["plantation_acceptable"] = context["plantation_evaluation"].result
        super().log_moulinette_event(moulinette, context, **kwargs)


class Triage(MoulinetteMixin, FormView):
    form_class = TriageFormHaie
    template_name = "haie/moulinette/triage.html"

    def get(self, request, *args, **kwargs):
        """This page should always have a department to be displayed."""

        if not self.moulinette.department:
            return HttpResponseRedirect(reverse("home"))

        log_event(
            "simulateur",
            "localisation",
            self.request,
            **{
                "department": self.moulinette.department,
            },
            **get_matomo_tags(self.request),
        )
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["matomo_custom_url"] = extract_matomo_url_from_request(self.request)

        return context

    def get_form(self):
        return self.moulinette.triage_form

    def form_valid(self, form):
        if self.moulinette.is_triage_valid():
            url = reverse("moulinette_form")
        else:
            url = reverse("moulinette_result")

        # We want to preserve existing querystring params when validating the form
        qs = self.request.GET.urlencode()
        url_with_params = f"{url}?{qs}"
        url_with_params = update_qs(url_with_params, form.cleaned_data)
        return HttpResponseRedirect(url_with_params)
