import base64
import binascii
import json

from django.core.exceptions import BadRequest
from django.http import HttpResponseRedirect, QueryDict
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from envergo.moulinette.forms import MoulinetteForm
from envergo.moulinette.models import Moulinette


class MoulinetteHome(FormView):
    template_name = "moulinette/home.html"
    form_class = MoulinetteForm

    def form_valid(self, form):

        form_data = form.cleaned_data
        footprint_dict = form.cleaned_data.get("project_footprint")
        footprint_json = json.dumps(footprint_dict)
        footprint_b64 = base64.urlsafe_b64encode(footprint_json.encode()).decode()
        url_data = {
            "created_surface": form_data["created_surface"],
            "existing_surface": form_data["existing_surface"],
            "project_footprint": footprint_b64,
        }
        get = QueryDict("", mutable=True)
        get.update(url_data)
        url_params = get.urlencode()
        url = reverse("moulinette_result")
        url_with_params = f"{url}?{url_params}"
        return HttpResponseRedirect(url_with_params)


class MoulinetteResult(TemplateView):
    def get(self, request, *args, **kwargs):
        try:
            params = self.check_moulinette_params(request)
        except (BadRequest, binascii.Error):
            return HttpResponseRedirect(reverse("moulinette_home"))

        self.moulinette = Moulinette(params)
        self.moulinette.run()
        return super().get(request, *args, **kwargs)

    def check_moulinette_params(self, request):
        """Parse and validate the moulinette url parameters."""

        data = request.GET.copy()
        footprint_b64 = data.get("project_footprint", "e30=")  # "e30=" -> {}
        footprint_json = base64.urlsafe_b64decode(footprint_b64).decode()
        data["project_footprint"] = footprint_json

        form = MoulinetteForm(data)
        if not form.is_valid():
            raise BadRequest("Invalid moulinette params")

        return form.cleaned_data

    def get_template_names(self):
        moulinette_result = self.moulinette.eval_result
        template_name = f"moulinette/result_{moulinette_result}.html"
        return [template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["moulinette"] = self.moulinette
        return context
