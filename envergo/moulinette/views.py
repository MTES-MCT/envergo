import json
from collections import OrderedDict
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.http import HttpResponseRedirect, QueryDict
from django.urls import reverse
from django.views.generic import FormView

from envergo.analytics.forms import FeedbackFormUseful, FeedbackFormUseless
from envergo.analytics.utils import is_request_from_a_bot, log_event
from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Department
from envergo.geodata.utils import get_address_from_coords
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import get_moulinette_class_from_site
from envergo.moulinette.utils import compute_surfaces
from envergo.utils.urls import extract_mtm_params, remove_from_qs, update_qs

BODY_TPL = {
    RESULTS.soumis: "moulinette/eval_body_soumis.html",
    RESULTS.action_requise: "moulinette/eval_body_action_requise.html",
    RESULTS.non_soumis: "moulinette/eval_body_non_soumis.html",
}


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

        moulinette_data = None
        GET = self.clean_request_get_parameters()
        if self.request.method == "GET" and GET:
            moulinette_data = GET
        elif self.request.method in ("POST", "PUT"):
            moulinette_data = self.request.POST

        if moulinette_data:
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

            if moulinette.is_evaluation_available() or self.request.user.is_staff:
                context["additional_forms"] = self.get_additional_forms(moulinette)
                context["additional_fields"] = self.get_additional_fields(moulinette)

                # We need to display a different form style when the "additional forms"
                # first appears, but the way this feature is designed, said forms
                # are always "bound" when they appear. So we have to check for the
                # presence of field keys in the GET parameters.
                additional_forms_bound = False
                field_keys = context["additional_fields"].keys()
                for key in field_keys:
                    if key in self.request.GET:
                        additional_forms_bound = True
                        break
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

        context["display_feedback_form"] = not self.request.GET.get("feedback", False)
        context["is_map_static"] = False
        context["visitor_id"] = self.request.COOKIES.get(
            settings.VISITOR_COOKIE_NAME, ""
        )

        if self.should_activate_optional_criteria():
            context["optional_forms"] = self.get_optional_forms(
                context.get("moulinette", None)
            )

        context = {**context, **MoulinetteClass.get_extra_context(self.request)}

        return context

    def render_to_response(self, context, **response_kwargs):
        # We have to store the moulinette since there are no other way
        # to give parameters to `get_template_names`
        self.moulinette = context.get("moulinette", None)
        self.triage_form = context.get("triage_form", None)
        return super().render_to_response(context, **response_kwargs)

    def get_additional_forms(self, moulinette):
        form_classes = moulinette.additional_form_classes()
        forms = []
        for Form in form_classes:
            form = Form(**self.get_form_kwargs())
            if form.fields:
                form.is_valid()
                forms.append(form)

        return forms

    def get_additional_fields(self, moulinette):
        """Return the list of additional criterion fields.

        Sometimes two criterions can ask the same question
        E.g the "Is this a lotissement project?"
        We need to make sure we don't display the same field twice though
        """

        forms = self.get_additional_forms(moulinette)
        fields = OrderedDict()
        for form in forms:
            for field in form:
                if field.name not in fields:
                    fields[field.name] = field

        return fields

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
        form_data.pop("address", None)
        form_data.pop("existing_surface", None)
        get.update(form_data)

        if hasattr(self, "moulinette"):
            moulinette = self.moulinette
        else:
            MoulinetteClass = get_moulinette_class_from_site(self.request.site)
            moulinette = MoulinetteClass(
                form_data, form.data, self.should_activate_optional_criteria()
            )

        additional_forms = self.get_additional_forms(moulinette)
        for additional_form in additional_forms:
            for field in additional_form:
                get.setlist(
                    field.html_name, additional_form.data.getlist(field.html_name)
                )

        if self.should_activate_optional_criteria():
            optional_forms = self.get_optional_forms(moulinette)
            for optional_form in optional_forms:
                for field in optional_form:
                    get.setlist(
                        field.html_name, optional_form.data.getlist(field.html_name)
                    )

        triage_params = moulinette.get_triage_params()
        if triage_params:
            get.update(
                {key: form.data[key] for key in triage_params if key in form.data}
            )

        url_params = get.urlencode()
        url = reverse("moulinette_result")

        # Scroll to the additional forms if there are missing data
        url_fragment = "#additional-forms" if moulinette.has_missing_data() else ""

        url_with_params = f"{url}?{url_params}{url_fragment}"
        return url_with_params

    def should_activate_optional_criteria(self):
        return self.request.user.is_staff

    def log_moulinette_event(self, moulinette, **kwargs):
        export = moulinette.summary()
        export.update(kwargs)
        export["url"] = self.request.build_absolute_uri()

        mtm_keys = {
            k: v for k, v in self.request.session.items() if k.startswith("mtm_")
        }
        export.update(mtm_keys)
        log_event(
            self.event_category,
            self.event_action,
            self.request,
            **export,
        )


class MoulinetteHome(MoulinetteMixin, FormView):
    template_name = "moulinette/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = self.render_to_response(context)

        if "redirect_url" in context:
            return HttpResponseRedirect(context["redirect_url"])
        elif self.moulinette:
            return HttpResponseRedirect(self.get_results_url(context["form"]))
        else:
            return res

    def form_valid(self, form):
        return HttpResponseRedirect(self.get_results_url(form))


class MoulinetteResult(MoulinetteMixin, FormView):
    event_category = "simulateur"
    event_action = "soumission"

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""

        moulinette = self.moulinette
        triage_form = self.triage_form
        is_debug = bool(self.request.GET.get("debug", False))
        is_edit = bool(self.request.GET.get("edit", False))
        is_admin = self.request.user.is_staff

        if moulinette is None and triage_form is None:
            template_name = "moulinette/home.html"
        elif moulinette is None:
            template_name = "haie/moulinette/triage_result.html"
        elif is_debug:
            template_name = moulinette.get_debug_result_template()
        elif is_edit:
            template_name = "moulinette/home.html"
        elif not moulinette.has_config():
            template_name = moulinette.get_result_non_disponible_template()
        elif not (moulinette.is_evaluation_available() or is_admin):
            template_name = moulinette.get_result_available_soon_template()
        elif moulinette.has_missing_data():
            template_name = "moulinette/home.html"
        else:
            template_name = moulinette.get_result_template()

        return [template_name]

    def get(self, request, *args, **kwargs):
        is_edit = bool(self.request.GET.get("edit", False))
        context = self.get_context_data()
        res = self.render_to_response(context)
        moulinette = self.moulinette
        triage_form = self.triage_form

        if "redirect_url" in context:
            return HttpResponseRedirect(context["redirect_url"])
        elif moulinette:
            if (
                "debug" not in self.request.GET
                and not is_edit
                and not self.validate_results_url(request, context)
            ):
                return HttpResponseRedirect(self.get_results_url(context["form"]))

            if not (
                moulinette.has_missing_data()
                or is_request_from_a_bot(request)
                or is_edit
            ):
                self.log_moulinette_event(moulinette)

            return res
        elif triage_form is not None:
            return res
        else:
            return HttpResponseRedirect(reverse("moulinette_home"))

    def validate_results_url(self, request, context):
        """Check that the url parameter does not contain any unexpected parameter.

        This is useful for cleaning urls from optional criteria parameters.
        """
        expected_url = self.get_results_url(context["form"])
        expected_qs = parse_qs(urlparse(expected_url).query)
        expected_params = set(expected_qs.keys())
        current_url = request.get_full_path()
        current_qs = parse_qs(urlparse(current_url).query)
        current_params = set(current_qs.keys())

        # We don't want to take analytics params into account, so they stay in the url
        current_params = set([p for p in current_params if not p.startswith("mtm_")])

        return expected_params == current_params

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        moulinette = context.get("moulinette", None)
        # Let's build custom uris for better matomo tracking
        # Depending on the moulinette result, we want to track different uris
        # as if they were distinct pages.
        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(current_url, {"mtm_campaign": "share-simu"})
        share_print_url = update_qs(current_url, {"mtm_campaign": "print-simu"})
        debug_result_url = update_qs(current_url, {"debug": "true"})
        result_url = remove_from_qs(current_url, "debug")
        edit_url = (
            update_qs(result_url, {"edit": "true"})
            if moulinette
            else context.get("triage_url", None)
        )
        # Url without any query parameters
        # We want to build "fake" urls for matomo tracking
        # For example, if the current url is /simulateur/resultat/?debug=true,
        # We want to track this as a custom url /simulateur/debug/
        mtm_params = extract_mtm_params(current_url)

        # We want to log the current simulation url stripped from any query parameters
        # except for mtm_ ones
        bare_url = self.request.build_absolute_uri(self.request.path)
        matomo_bare_url = update_qs(bare_url, mtm_params)
        debug_url = self.request.build_absolute_uri(reverse("moulinette_result_debug"))
        matomo_debug_url = update_qs(debug_url, mtm_params)
        missing_data_url = self.request.build_absolute_uri(
            reverse("moulinette_missing_data")
        )
        form_url = self.request.build_absolute_uri(reverse("moulinette_home"))
        form_url_with_edit = update_qs(form_url, {"edit": "true"})
        matomo_missing_data_url = update_qs(missing_data_url, mtm_params)

        context["current_url"] = current_url
        context["share_btn_url"] = share_btn_url
        context["share_print_url"] = share_print_url
        context["envergo_url"] = self.request.build_absolute_uri("/")
        context["base_result"] = "moulinette/base_result.html"
        is_debug = bool(self.request.GET.get("debug", False))
        is_edit = bool(self.request.GET.get("edit", False))

        if moulinette:
            context["base_result"] = moulinette.get_result_template()
            context["display_actions_banner"] = moulinette.result == RESULTS.soumis

        if moulinette and is_edit:
            context["matomo_custom_url"] = form_url_with_edit
        elif moulinette and is_debug:
            context = {
                **context,
                **moulinette.get_debug_context(),
                "result_url": result_url,
                "matomo_custom_url": matomo_debug_url,
            }

        # TODO This cannot happen, since we redirect to the form if data is missing
        # Check that it can be safely removed
        elif moulinette and moulinette.has_missing_data():
            context["matomo_custom_url"] = matomo_missing_data_url

        elif moulinette:
            context["matomo_custom_url"] = matomo_bare_url
            if moulinette.has_config() and moulinette.is_evaluation_available():
                context["debug_url"] = debug_result_url

        if moulinette and moulinette.catalog:
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

        context["is_admin"] = self.request.user.is_staff
        context["edit_url"] = edit_url

        return context


class Triage(FormView):
    form_class = TriageFormHaie
    template_name = "haie/moulinette/triage.html"

    def get(self, request, *args, **kwargs):
        """This page should always have a department to be displayed."""
        context = self.get_context_data()
        if not context.get("department", None):
            return HttpResponseRedirect(reverse("home"))
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
        context["department"] = department

        return context

    def get_initial(self):
        """Populate the form with data from the query string."""
        return self.request.GET.dict()

    def form_valid(self, form):
        query_params = form.cleaned_data
        if query_params["element"] == "haie" and query_params["travaux"] == "arrachage":
            url = reverse("moulinette_home")
        else:
            url = reverse("moulinette_result")

        query_string = urlencode(query_params)
        url_with_params = f"{url}?{query_string}"
        return HttpResponseRedirect(url_with_params)
