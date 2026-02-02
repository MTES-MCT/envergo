import json
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
from urllib.parse import urlencode

from django.conf import settings
from django.forms.widgets import CheckboxInput
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import DetailView, FormView

from envergo.analytics.forms import FeedbackFormUseful, FeedbackFormUseless
from envergo.analytics.utils import (
    get_matomo_tags,
    get_user_type,
    is_request_from_a_bot,
    log_event,
    update_url_with_matomo_params,
)
from envergo.evaluations.models import TagStyleEnum
from envergo.geodata.utils import get_address_from_coords
from envergo.hedges.services import PlantationEvaluator
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import ConfigHaie, Criterion, Regulation
from envergo.moulinette.utils import get_moulinette_class_from_site
from envergo.users.mixins import InstructorDepartmentAuthorised
from envergo.utils.urls import copy_qs, remove_from_qs, remove_mtm_params, update_qs


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
        return moulinette_data

    def get_form_data(self):
        """Get the data to pass to the moulinette forms."""

        moulinette_data = self.request.POST.dict()
        return moulinette_data

    def clean_request_get_parameters(self):
        """Remove parameters that don't belong to the moulinette form.

        Mainly, we want to ignore parameters set by different analytics systems
        because they are messing with the moulinette form processing.
        """
        ignore_prefixes = ["mtm_", "utm_", "pk_", "piwik_", "matomo_", "zoom"]
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

        # Is there a zoom value set in the url?
        try:
            zoom = int(self.request.GET.get("zoom"))
            config = settings.LEAFLET_CONFIG
            # Make sure the zoom level stays in bounds
            zoom = max(zoom, config["MIN_ZOOM"])
            zoom = min(zoom, config["MAX_ZOOM"])
        except (ValueError, TypeError):
            zoom = None

        # Should we center the map on the given coordinates, or zoom out on
        # the entire country?
        if "lng" in context and "lat" in context:
            lng, lat = context["lng"], context["lat"]
            context["display_marker"] = True
            context["center_map"] = [lng, lat]
            context["default_zoom"] = zoom or 16
        else:
            # By default, show all metropolitan france in map
            context["display_marker"] = False
            context["center_map"] = [1.7000, 47.000]
            context["default_zoom"] = zoom or 5

        context["is_map_static"] = False
        context["visitor_id"] = self.request.COOKIES.get(
            settings.VISITOR_COOKIE_NAME, ""
        )

        context["expand_optional_forms"] = (
            self.request.user.is_staff
            and self.request.user.groups.filter(name="Staff ops").exists()
        )
        context["optional_forms"] = self.moulinette.optional_forms
        context["triage_form"] = self.moulinette.triage_form

        context = {**context, **self.moulinette.get_extra_context(self.request)}

        urls_data = self.get_urls_context_data(context)
        context.update(urls_data)

        return context

    def get_urls_context_data(self, context):
        """Custom context data related to urls.

        We need to build different urls to make linking easier.
        For example, we display a "share" button that links to the current page
        with additional mtm params, a "debug" button that links to the
        debug page, etc.
        """
        data = {}
        moulinette = self.moulinette

        current_url = self.request.build_absolute_uri()
        current_url_mtm_free = remove_mtm_params(current_url)
        share_btn_url = update_qs(current_url_mtm_free, {"mtm_campaign": "share-simu"})
        share_print_url = update_qs(
            current_url_mtm_free, {"mtm_campaign": "print-simu"}
        )
        result_url = remove_from_qs(current_url, "debug")
        debug_result_url = update_qs(current_url, {"debug": "true"})
        form_url = reverse("moulinette_form")
        form_url = copy_qs(form_url, current_url)
        triage_url = reverse("moulinette_home")
        triage_url = copy_qs(triage_url, current_url)

        if moulinette.triage_form and not moulinette.is_triage_valid():
            edit_url = triage_url
        else:
            edit_url = form_url

        data["triage_url"] = triage_url
        data["edit_url"] = edit_url
        data["result_url"] = result_url
        data["current_url"] = current_url
        data["share_btn_url"] = share_btn_url
        data["share_print_url"] = share_print_url
        data["envergo_url"] = self.request.build_absolute_uri("/")
        data["debug_url"] = debug_result_url

        return data

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
        url_data = self.clean_request_get_parameters()
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

    def get_triage_url(self):
        """Return the triage url while preserving existing parameters.

        This method MUST NOT be called when a "triage" url is not defined,
        e.g for amenagement.
        """
        data = self.get_results_params()
        params = urlencode(data)
        url = reverse("triage")

        url_with_params = f"{url}?{params}"
        return url_with_params

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
            # if the triage is not valid, we log a "soumission_autre" action
            action = (
                self.event_action_haie
                if moulinette.is_triage_valid()
                else "soumission_autre"
            )

        mtm_keys = get_matomo_tags(self.request)
        export.update(mtm_keys)

        log_event(
            self.event_category,
            action,
            self.request,
            **export,
            user_type=get_user_type(self.request.user),
        )


@method_decorator(xframe_options_sameorigin, name="dispatch")
class MoulinetteForm(MoulinetteMixin, FormView):

    def get(self, request, *args, **kwargs):
        moulinette = self.moulinette

        # We make sure the triage data is valid before allowing this step
        if moulinette.is_triage_valid():
            response = super().get(request, *args, **kwargs)
        else:
            response = HttpResponseRedirect(self.get_triage_url())

        return response

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
        elif self.moulinette.main_form.is_valid() and (
            self.moulinette.additional_fields
            and not self.moulinette.are_additional_forms_bound()
        ):
            return HttpResponseRedirect(f"{self.get_form_url()}#additional-forms")

        # In other cases, it means there are errors in one of the submitted forms,
        # so we just display back the page with the validation errors
        else:
            return self.form_invalid(self.moulinette.main_form)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)

        form_errors = defaultdict(list)
        for field, errors in self.moulinette.form_errors().items():
            for error in errors.as_data():
                form_errors[field].append(
                    {"code": str(error.code), "message": str(error.message)}
                )
        log_event(
            "erreur",
            "formulaire-simu",
            self.request,
            data=form.data,
            errors=form_errors,
            user_type=get_user_type(self.request.user),
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matomo_url = self.request.path

        # Custom url when some values are pre-filled
        GET_fields = set(self.request.GET.keys())

        # Don't send the pre-fill url when it's only triage fields though
        triage_form = self.moulinette.triage_form
        if triage_form:
            triage_fields = set(triage_form.fields.keys())
            GET_fields -= triage_fields

        if GET_fields:
            matomo_url = reverse("moulinette_prefilled_form")

        # There are some additional forms displayed
        if self.moulinette.additional_fields:
            matomo_url = reverse("moulinette_missing_data")

        form = context["form"]
        if form.is_bound and not form.is_valid():
            matomo_url = reverse("moulinette_invalid_form")

        full_matomo_url = self.request.build_absolute_uri(matomo_url)
        context["matomo_custom_url"] = update_url_with_matomo_params(
            full_matomo_url, self.request
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
        elif not moulinette.is_valid():
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
        elif is_debug:
            data["matomo_custom_url"] = update_url_with_matomo_params(
                debug_url, self.request
            )

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

        return context


class BaseMoulinetteResult(FormView):
    def get(self, request, *args, **kwargs):
        moulinette = self.moulinette
        triage_form = moulinette.triage_form
        redirect_url = None

        # Triage is required and triage form is invalid
        if triage_form and not triage_form.is_valid():
            if "department" in triage_form.errors:
                redirect_url = f"{reverse("home")}#simulateur"
            else:
                redirect_url = reverse("triage")
                redirect_url = update_qs(redirect_url, request.GET)

        # Moulinette is invalid and there is no triage to do (amenagement) or the triage is valid (haie)
        # so just redirect to the form
        elif moulinette.is_triage_valid() and not moulinette.is_valid():
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
            return HttpResponseRedirect(f"{reverse("home")}#simulateur")

        event_params = {
            "department": self.moulinette.department.department,
            "user_type": get_user_type(request.user),
        }
        is_alternative = bool(request.GET.get("alternative", False))
        if is_alternative:
            event_params["alternative"] = "true"

        log_event(
            "simulateur",
            "localisation",
            self.request,
            **event_params,
            **get_matomo_tags(self.request),
        )
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matomo_url = self.request.path

        # Custom url when some values are pre-filled
        GET_fields = set(self.request.GET.keys()) - set(["department"])
        if GET_fields:
            matomo_url = reverse("moulinette_prefilled_triage")

        full_matomo_url = self.request.build_absolute_uri(matomo_url)
        context["matomo_custom_url"] = update_url_with_matomo_params(
            full_matomo_url, self.request
        )

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


class ConfigHaieSettingsView(InstructorDepartmentAuthorised, DetailView):
    """Config haie settings view for a given department"""

    queryset = ConfigHaie.objects.all()
    template_name = "haie/moulinette/confighaie_settings.html"

    def get_object(self, queryset=None):
        """Return Config haie related to department number"""

        if self.department is None:
            self.department = self.get_department(self.kwargs)

        queryset = self.queryset.filter(department=self.department)

        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": queryset.model._meta.verbose_name}
            )
        return obj

    def get_context_data(self, **kwargs):
        """Add department members emails and activation maps related to this department"""

        # Add department members emails
        context = super().get_context_data()
        department = self.department
        context["department"] = self.department
        department_members = (
            department.members.filter(is_superuser=False)
            .filter(is_staff=False)
            .order_by("email")
        )
        departement_members_dict = {
            "instructors_emails": [],
            "invited_emails": [],
        }
        for user in department_members:
            if user.is_instructor:
                departement_members_dict["instructors_emails"].append(user.email)
            else:
                departement_members_dict["invited_emails"].append(user.email)
        context["department_members"] = departement_members_dict

        # Get activation maps for criteria in regulations related to this department
        MAPS_REGULATION_LIST = [
            "natura2000_haie",
            "reserves_naturelles",
            "code_rural_haie",
            "sites_proteges_haie",
        ]
        regulation_list = Regulation.objects.filter(
            regulation__in=MAPS_REGULATION_LIST
        ).order_by("display_order")

        # Retrieve criteria filtered by regulation in MAPS_REGULATION_LIST, filtered by department,
        # ordered by regulation display order, with unique activation map to be regrouped by regulation
        criteria_list = (
            Criterion.objects.select_related("regulation")
            .select_related("activation_map")
            .only(
                "regulation__regulation",
                "activation_map__name",
                "activation_map__file",
                "activation_map__description",
                "activation_map__source",
                "activation_map__departments",
            )
            .filter(regulation__in=regulation_list)
            .filter(activation_map__departments__contains=[self.department.department])
            .order_by(
                "regulation__display_order",
                "regulation__regulation",
                "activation_map__name",
            )
            .distinct(
                "regulation__display_order",
                "regulation__regulation",
                "activation_map__name",
            )
        )

        grouped_criteria_by_regulation = {
            k: list(v)
            for k, v in groupby(criteria_list, key=attrgetter("regulation.regulation"))
        }
        context["regulation_list"] = regulation_list
        context["grouped_criteria"] = grouped_criteria_by_regulation
        return context
