from django.http import HttpResponseRedirect, QueryDict
from django.urls import reverse
from django.views.generic import FormView

from envergo.analytics.utils import log_event
from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms import MoulinetteForm
from envergo.moulinette.models import Moulinette

BODY_TPL = {
    RESULTS.soumis: "moulinette/eval_body_soumis.html",
    RESULTS.action_requise: "moulinette/eval_body_action_requise.html",
    RESULTS.non_soumis: "moulinette/eval_body_non_soumis.html",
}


class MoulinetteHome(FormView):
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
        GET = self.request.GET.copy()
        keys = GET.keys()
        for key in list(keys):
            for prefix in ignore_prefixes:
                if key.startswith(prefix):
                    GET.pop(key)
        return GET

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = context["form"]
        if form.is_valid():
            moulinette = Moulinette(form.cleaned_data)
            context["moulinette"] = moulinette
            context.update(moulinette.catalog)

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

        return context

    def render_to_response(self, context, **response_kwargs):
        # We have to store the moulinette since there are no other way
        # to give parameters to `get_template_names`
        self.moulinette = context.get("moulinette", None)
        return super().render_to_response(context, **response_kwargs)

    def get_template_names(self):
        """Check wich template to use depending on the moulinette result."""

        moulinette = self.moulinette
        is_debug = bool(self.request.GET.get("debug", False))

        if moulinette is None:
            template_name = "moulinette/home.html"
        elif is_debug:
            template_name = "moulinette/result_debug.html"
        elif not moulinette.is_evaluation_available():
            template_name = "moulinette/result_non_disponible.html"
        else:
            template_name = "moulinette/result.html"

        return [template_name]

    def get(self, request, *args, **kwargs):
        res = super().get(request, *args, **kwargs)
        moulinette = self.moulinette
        if moulinette:
            data = moulinette.catalog
            export = {
                "lat": f'{data["lng"]:.5f}',
                "lng": f'{data["lng"]:.5f}',
                "existing_surface": data["existing_surface"],
                "created_surface": data["created_surface"],
                "is_eval_available": moulinette.is_evaluation_available(),
            }
            if moulinette.is_evaluation_available():
                export["result"] = moulinette.result()

            log_event("simulateur", "soumission", request.session.session_key, **export)
        return res

    def form_valid(self, form):

        get = QueryDict("", mutable=True)
        form_data = form.cleaned_data
        form_data.pop("address")
        get.update(form_data)
        url_params = get.urlencode()
        url = reverse("moulinette_home")
        url_with_params = f"{url}?{url_params}"
        return HttpResponseRedirect(url_with_params)
