import json
from collections import OrderedDict

from django.conf import settings
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.http import HttpResponseRedirect, QueryDict
from django.urls import reverse
from django.views.generic import FormView

from envergo.analytics.forms import FeedbackFormUseful, FeedbackFormUseless
from envergo.analytics.utils import is_request_from_a_bot, log_event
from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms import MoulinetteDebugForm, MoulinetteForm
from envergo.moulinette.models import FakeMoulinette, Moulinette

BODY_TPL = {
    RESULTS.soumis: "moulinette/eval_body_soumis.html",
    RESULTS.action_requise: "moulinette/eval_body_action_requise.html",
    RESULTS.non_soumis: "moulinette/eval_body_non_soumis.html",
}


class MoulinetteMixin:
    """Display the moulinette form and results."""

    form_class = MoulinetteForm

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
            kwargs.update({"data": moulinette_data})

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

        form = context["form"]
        if form.is_valid():
            moulinette = Moulinette(form.cleaned_data, form.data)
            context["moulinette"] = moulinette
            context.update(moulinette.catalog)

            if moulinette.is_evaluation_available() or self.request.user.is_superuser:
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
            context["default_zoom"] = 6

        context["display_feedback_form"] = not self.request.GET.get("feedback", False)
        context["is_map_static"] = False
        context["source"] = "moulinette"
        context["visitor_id"] = self.request.COOKIES.get(
            settings.VISITOR_COOKIE_NAME, ""
        )

        return context

    def render_to_response(self, context, **response_kwargs):
        # We have to store the moulinette since there are no other way
        # to give parameters to `get_template_names`
        self.moulinette = context.get("moulinette", None)
        return super().render_to_response(context, **response_kwargs)

    def get_additional_forms(self, moulinette):
        form_classes = moulinette.additional_form_classes()
        kwargs = self.get_form_kwargs()
        forms = []
        for Form in form_classes:
            form = Form(**kwargs)
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

    def form_valid(self, form):
        return HttpResponseRedirect(self.get_results_url(form))

    def get_results_url(self, form):
        """Generates the GET url corresponding to the POST'ed moulinette query."""

        get = QueryDict("", mutable=True)
        form_data = form.cleaned_data
        form_data.pop("address")
        form_data.pop("existing_surface")
        get.update(form_data)

        moulinette = Moulinette(form_data, form.data)
        additional_forms = self.get_additional_forms(moulinette)
        for form in additional_forms:
            form.is_valid()  # trigger form validation
            get.update(form.cleaned_data)

        url_params = get.urlencode()
        url = reverse("moulinette_result")

        # We add the `#` at the end to reset the accordions' states
        url_with_params = f"{url}?{url_params}#"
        return url_with_params


class MoulinetteHome(MoulinetteMixin, FormView):
    template_name = "moulinette/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = self.render_to_response(context)
        if self.moulinette:
            return HttpResponseRedirect(self.get_results_url(context["form"]))
        else:
            return res


class MoulinetteResult(MoulinetteMixin, FormView):
    event_category = "simulateur"
    event_action = "soumission"

    def get_template_names(self):
        """Check which template to use depending on the moulinette result."""

        moulinette = self.moulinette
        is_debug = bool(self.request.GET.get("debug", False))
        is_admin = self.request.user.is_superuser

        if moulinette is None:
            template_name = "moulinette/home.html"
        elif is_debug:
            template_name = "moulinette/result_debug.html"
        elif not moulinette.has_config():
            template_name = "moulinette/result_non_disponible.html"
        elif not (moulinette.is_evaluation_available() or is_admin):
            template_name = "moulinette/result_available_soon.html"
        elif moulinette.has_missing_data():
            template_name = "moulinette/missing_data.html"
        else:
            template_name = "moulinette/result.html"

        return [template_name]

    def log_moulinette_event(self, moulinette, **kwargs):
        export = moulinette.summary()
        export.update(kwargs)
        export["url"] = self.request.build_absolute_uri()
        log_event(self.event_category, self.event_action, self.request, **export)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = self.render_to_response(context)
        moulinette = self.moulinette
        if moulinette:
            if not (moulinette.has_missing_data() or is_request_from_a_bot(request)):
                self.log_moulinette_event(moulinette)

            return res
        else:
            return HttpResponseRedirect(reverse("moulinette_home"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_url = self.request.build_absolute_uri()
        tracked_url = f"{current_url}&mtm_source=shareBtn"
        context["current_url"] = tracked_url

        moulinette = context.get("moulinette", None)
        is_debug = bool(self.request.GET.get("debug", False))
        if moulinette and is_debug:
            # In the debug page, we want to factorize the maps we display, so we order them
            # by map first
            context["grouped_perimeters"] = moulinette.perimeters.order_by(
                "activation_map__name",
                "distance",
            )
            context["grouped_criteria"] = moulinette.criteria.order_by(
                "activation_map__name",
                "distance",
            )
            context["grouped_zones"] = (
                moulinette.catalog["all_zones"]
                .annotate(type=Concat("map__map_type", V("-"), "map__data_type"))
                .order_by("type", "distance", "map__name")
            )

        return context


class MoulinetteDebug(FormView):
    """Visualize the moulinette result for a specific criteria result combination.

    See `envergo.moulinette.models.FakeMoulinette` for more details.
    """

    form_class = MoulinetteDebugForm

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        # This form is submitted with GET, not POST
        GET = self.request.GET
        if GET:
            kwargs.update({"data": GET})

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        if form.is_valid():
            context["moulinette"] = self.moulinette = FakeMoulinette(form.cleaned_data)
            context.update(self.moulinette.catalog)

        return context

    def get_template_names(self):
        """Check wich template to use depending on the moulinette result."""

        moulinette = getattr(self, "moulinette", None)
        is_superuser = self.request.user.is_superuser

        if moulinette and (moulinette.is_evaluation_available() or is_superuser):
            template_name = "moulinette/debug_result.html"
        elif moulinette:
            template_name = "moulinette/debug_result_non_disponible.html"
        else:
            template_name = "moulinette/debug.html"

        return [template_name]


class MoulinetteRegulationResult(MoulinetteResult, FormView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        moulinette = context["moulinette"]

        regulation_slug = self.kwargs.get("regulation")
        context["regulations"] = [getattr(moulinette, regulation_slug)]

        return context
