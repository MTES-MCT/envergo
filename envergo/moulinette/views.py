import json
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.http import HttpResponseRedirect, QueryDict
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
from envergo.geodata.models import Department
from envergo.geodata.utils import get_address_from_coords
from envergo.hedges.services import PlantationEvaluator
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import (
    ConfigHaie,
    MoulinetteHaie,
    get_moulinette_class_from_site,
)
from envergo.moulinette.utils import compute_surfaces
from envergo.utils.urls import copy_qs, remove_from_qs, update_qs


class MoulinetteMixin:
    """Display the moulinette form and results."""

    def get_form_class(self):
        MoulinetteClass = get_moulinette_class_from_site(self.request.site)
        FormClass = MoulinetteClass.get_main_form_class()
        return FormClass

    def get_initial(self):
        return self.request.GET

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        # We always want to submit data present in url, event if they don't belong
        # to an actual form.
        # This is because sometimes, when the form value change, we can add or remove
        # some additional questions, and we don't want the user to lose those values
        # in between submissions
        moulinette_data = self.clean_request_get_parameters()
        if self.request.method in ("POST", "PUT"):
            moulinette_data.update(self.request.POST)

        mutable_data = moulinette_data.copy()
        mutable_data.update(compute_surfaces(moulinette_data))
        kwargs.update({"data": mutable_data})

        return kwargs

    def clean_request_get_parameters(self):
        """Remove parameters that don't belong to the moulinette form.

        Mainly, we want to ignore parameters set by different analytics systems
        because they are messing with the moulinette form processing.
        """
        ignore_prefixes = ["mtm_", "utm_", "pk_", "piwik_", "matomo_"]
        GET = self.get_moulinette_raw_data()
        keys = GET.keys()
        for key in list(keys):
            for prefix in ignore_prefixes:
                if key.startswith(prefix):
                    GET.pop(key)
        return GET

    def get_moulinette_raw_data(self):
        return self.request.GET.copy()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        MoulinetteClass = get_moulinette_class_from_site(self.request.site)

        form = context["form"]
        if form.is_valid():
            moulinette = MoulinetteClass(
                form.cleaned_data, form.data, self.should_activate_optional_criteria()
            )
            context["moulinette"] = moulinette
            context.update(moulinette.catalog)

            context["additional_forms"] = moulinette.additional_forms()
            context["additional_fields"] = moulinette.additional_fields()

            # We need to display a different form style when the "additional forms"
            # first appears, but the way this feature is designed, said forms
            # are always "bound" when they appear. So we have to check for the
            # presence of field keys in the GET parameters.
            additional_forms_bound = any(
                key in self.request.GET for key in context["additional_fields"].keys()
            )
            context["additional_forms_bound"] = additional_forms_bound

            moulinette_data = moulinette.summary()
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
        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]
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

        context["optional_forms"] = self.get_optional_forms(
            context.get("moulinette", None)
        )
        context["expand_optional_forms"] = (
            self.request.user.is_staff
            and self.request.user.groups.filter(name="Staff ops").exists()
        )

        context = {**context, **MoulinetteClass.get_extra_context(self.request)}

        return context

    def render_to_response(self, context, **response_kwargs):
        # We have to store the moulinette since there are no other way
        # to give parameters to `get_template_names`
        self.moulinette = context.get("moulinette", None)
        self.triage_form = context.get("triage_form", None)
        return super().render_to_response(context, **response_kwargs)

    def get_optional_forms(self, moulinette=None):
        """Get the form list for optional criteria.

        If a moulinette object is available, it means the user submitted the form,
        so we can fetch the optional criteria from the moulinette object.

        But we also want to display optional forms on the initial moulinette form,
        so we have no choice but to manually fetch all optional criteria and extracting
        their forms.
        """
        if moulinette:
            form_classes = moulinette.optional_form_classes()
        else:
            form_classes = self.get_all_optional_form_classes()

        forms = []
        for Form in form_classes:
            form_kwargs = self.get_form_kwargs()

            # Every optional form has a "activate" field
            # If unchecked, the form validation must be ignored alltogether
            activate_field = f"{Form.prefix}-activate"
            if "data" in form_kwargs and activate_field not in form_kwargs["data"]:
                form_kwargs.pop("data")

            form = Form(**form_kwargs)
            if form.fields:
                form.is_valid()
                forms.append(form)

        return forms

    def get_all_optional_form_classes(self):
        form_classes = []
        MoulinetteClass = get_moulinette_class_from_site(self.request.site)
        for criterion in MoulinetteClass.get_optionnal_criteria():
            form_class = criterion.evaluator.form_class
            if form_class and form_class not in form_classes:
                form_classes.append(form_class)

        return form_classes

    def get_results_url(self, form):
        """Generates the GET url corresponding to the POST'ed moulinette query.

        We submit the form via a POST method (TBH I don't remember why but there was a reason).
        But since we want the moulinette result to have a distinct url, we immediately redirect
        to the full url.

        We only want to keep useful parameters, i.e the ones that are actually used
        by the moulinette forms.
        """

        get = QueryDict("", mutable=True)
        form_data = form.cleaned_data
        get_data = form_data.copy()  # keep the computed values in the catalog
        get_data.pop("address", None)
        get_data.pop("existing_surface", None)
        get.update(get_data)

        if hasattr(self, "moulinette"):
            moulinette = self.moulinette
        else:
            MoulinetteClass = get_moulinette_class_from_site(self.request.site)
            moulinette = MoulinetteClass(
                form_data, form.data, self.should_activate_optional_criteria()
            )

        additional_forms = moulinette.additional_forms()
        for additional_form in additional_forms:
            for field in additional_form:
                value = additional_form.data.get(field.html_name, None)
                if value:
                    get[field.html_name] = value

        optional_forms = self.get_optional_forms(moulinette)
        for optional_form in optional_forms:
            for field in optional_form:
                value = optional_form.data.get(field.html_name, None)
                if value:
                    get[field.html_name] = value

        triage_params = moulinette.get_triage_params()
        if triage_params:
            get.update(
                {key: form.data[key] for key in triage_params if key in form.data}
            )

        if "alternative" in self.request.GET:
            get["alternative"] = self.request.GET["alternative"]

        url_params = get.urlencode()
        url = reverse("moulinette_result")

        # Scroll to the additional forms if there are missing data
        url_fragment = "#additional-forms" if moulinette.has_missing_data() else ""

        url_with_params = f"{url}?{url_params}{url_fragment}"
        return url_with_params

    def should_activate_optional_criteria(self):
        return True

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
        MoulinetteClass = get_moulinette_class_from_site(self.request.site)
        return MoulinetteClass.get_home_template()

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = self.render_to_response(context)

        if "redirect_url" in context:
            return HttpResponseRedirect(context["redirect_url"])
        elif self.moulinette and not context.get("is_alternative", False):
            return HttpResponseRedirect(self.get_results_url(context["form"]))
        else:
            return res

    def form_valid(self, form):
        return HttpResponseRedirect(self.get_results_url(form))

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

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""

        moulinette = self.moulinette
        triage_form = self.triage_form
        is_debug = bool(self.request.GET.get("debug", False))
        is_admin = self.request.user.is_staff

        # We want to display the moulinette result template, but must check all
        # previous cases where we cannot do it

        if moulinette is None and triage_form is None:
            MoulinetteClass = get_moulinette_class_from_site(self.request.site)
            template_name = MoulinetteClass.get_home_template()
        elif moulinette is None:
            template_name = MoulinetteHaie.get_triage_template(triage_form)
        elif is_debug:
            template_name = moulinette.get_debug_result_template()
        elif not moulinette.has_config():
            template_name = moulinette.get_result_non_disponible_template()
        elif not (moulinette.is_evaluation_available() or is_admin):
            template_name = moulinette.get_result_available_soon_template()
        elif moulinette.has_missing_data():
            template_name = moulinette.get_home_template()
        else:
            template_name = moulinette.get_result_template()

        return [template_name]

    def validate_results_url(self, request, context):
        """Check that the url parameter does not contain any unexpected parameter.

        This is useful for cleaning urls from optional criteria parameters.
        """
        expected_url = self.get_results_url(context["form"])
        expected_qs = parse_qs(urlparse(expected_url).query)
        expected_params = set(expected_qs.keys())
        moulinette_data = self.get_moulinette_data()
        current_params = set(moulinette_data.keys())

        # We don't want to take analytics params into account, so they stay in the url
        current_params = set([p for p in current_params if not p.startswith("mtm_")])
        return expected_params == current_params

    def get_moulinette_data(self):
        current_url = self.request.get_full_path()
        current_qs = (
            self.request.moulinette_data
            if hasattr(self.request, "moulinette_data")
            else parse_qs(urlparse(current_url).query)
        )
        return current_qs

    def get_analytics_context_data(self, context):
        """Custom context data related to analytics.

        We have to build a bunch of "fake" urls for tracking purpose.
        For example, we want the debug page to be logged as a `/simulateur/debug/`
        url in matomo, even though the real url is `/simulateur/resultat/?debug=true`.
        """
        data = {}
        moulinette = context.get("moulinette", None)
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

        if moulinette and is_debug:
            data["matomo_custom_url"] = update_url_with_matomo_params(
                debug_url, self.request
            )

        elif moulinette and moulinette.has_missing_data():
            if context["additional_forms_bound"]:
                data["matomo_custom_url"] = update_url_with_matomo_params(
                    invalid_form_url, self.request
                )
            else:
                data["matomo_custom_url"] = update_url_with_matomo_params(
                    missing_data_url, self.request
                )

        elif not moulinette and context.get("triage_form", None):
            data["matomo_custom_url"] = update_url_with_matomo_params(
                out_of_scope_result_url, self.request
            )

        if is_alternative:
            data["matomo_custom_url"] = update_qs(
                data["matomo_custom_url"], {"alternative": "true"}
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
        moulinette = context.get("moulinette", None)

        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(current_url, {"mtm_campaign": "share-simu"})
        share_print_url = update_qs(current_url, {"mtm_campaign": "print-simu"})
        result_url = remove_from_qs(current_url, "debug")
        debug_result_url = update_qs(current_url, {"debug": "true"})
        form_url = reverse("moulinette_form")
        form_url = copy_qs(form_url, current_url)
        edit_url = (
            update_qs(form_url, {"edit": "true"})
            if moulinette
            else context.get("triage_url", None)
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
        context = self.get_context_data(**kwargs)
        res = self.render_to_response(context)
        moulinette = self.moulinette
        triage_form = self.triage_form

        if "redirect_url" in context:
            return HttpResponseRedirect(context["redirect_url"])

        elif moulinette:
            if "debug" not in self.request.GET and not self.validate_results_url(
                request, context
            ):
                return HttpResponseRedirect(self.get_results_url(context["form"]))

            required_form_errors = moulinette.required_form_errors()
            optional_form_errors = moulinette.optional_form_errors()

            if not (moulinette.has_missing_data() or is_request_from_a_bot(request)):
                self.log_moulinette_event(moulinette, context)
            elif (
                bool(required_form_errors)
                and context["additional_forms_bound"]
                or bool(optional_form_errors)
            ):
                log_event(
                    "erreur",
                    "formulaire-simu",
                    self.request,
                    data=moulinette.raw_data,
                    errors={
                        field: [
                            {"code": str(e.code), "message": str(e.message)}
                            for e in errors.data
                        ]
                        for field, errors in (
                            required_form_errors | optional_form_errors
                        ).items()
                    },
                )

            return res

        elif triage_form is not None:
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
            return res
        else:
            return HttpResponseRedirect(reverse("moulinette_form"))


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
        context["edit_url"] = update_qs(form_url, {"edit": "true"})
        return context

    def log_moulinette_event(self, moulinette, context, **kwargs):
        kwargs["plantation_acceptable"] = context["plantation_evaluation"].result
        super().log_moulinette_event(moulinette, context, **kwargs)


class Triage(FormView):
    form_class = TriageFormHaie
    template_name = "haie/moulinette/triage.html"

    def get(self, request, *args, **kwargs):
        """This page should always have a department to be displayed."""
        context = self.get_context_data()
        if not context.get("department", None):
            return HttpResponseRedirect(reverse("home"))
        log_event(
            "simulateur",
            "localisation",
            self.request,
            **{
                "department": context["department"].department,
            },
            **get_matomo_tags(self.request),
        )
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_code = self.request.GET.get("department", None)
        department = (
            (
                Department.objects.defer("geometry")
                .filter(department=department_code)
                .first()
            )
            if department_code
            else None
        )
        config = ConfigHaie.objects.filter(department=department).first()

        context["department"] = department
        context["config"] = config
        context["matomo_custom_url"] = extract_matomo_url_from_request(self.request)

        return context

    def get_initial(self):
        """Populate the form with data from the query string."""
        return self.request.GET.dict()

    def form_valid(self, form):
        query_params = form.cleaned_data
        if (
            query_params["element"] == "haie"
            and query_params["travaux"] == "destruction"
        ):
            url = reverse("moulinette_form")
        else:
            url = reverse("moulinette_result")

        # We want to preserve existing querystring params when validating the form
        qs = self.request.GET.urlencode()
        url_with_params = f"{url}?{qs}"
        url_with_params = update_qs(url_with_params, query_params)
        return HttpResponseRedirect(url_with_params)
