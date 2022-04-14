from django.http import HttpResponseRedirect, QueryDict
from django.urls import reverse
from django.views.generic import FormView

from envergo.moulinette.forms import MoulinetteForm
from envergo.moulinette.models import Moulinette


class MoulinetteHome(FormView):
    """Display the moulinette form and results.

    When the form is submitted, we urlencode the form parameters and redirect
    to the same url with the added GET parameters.

    Also, the "coords" attribute is base64 encoded.
    """

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
        if self.request.method == "GET" and self.request.GET:
            moulinette_data = self.request.GET
        elif self.request.method in ("POST", "PUT"):
            moulinette_data = self.request.POST

        if moulinette_data:
            kwargs.update({"data": moulinette_data})

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = context["form"]
        if form.is_valid():
            moulinette = Moulinette(form.cleaned_data)
            moulinette.run()
            context["moulinette"] = moulinette

            if moulinette.result_soumis:
                context["contact_data"] = moulinette.department.contact_html

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
        else:
            template_name = f"moulinette/result.html"

        return [template_name]

    def form_valid(self, form):

        get = QueryDict("", mutable=True)
        form_data = form.cleaned_data
        form_data.pop("address")
        get.update(form_data)
        url_params = get.urlencode()
        url = reverse("moulinette_home")
        url_with_params = f"{url}?{url_params}"
        return HttpResponseRedirect(url_with_params)
