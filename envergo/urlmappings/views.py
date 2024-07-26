from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView
from django_ratelimit.decorators import ratelimit

from envergo.urlmappings.forms import UrlMappingCreateForm


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST"), name="post")
class UrlMappingCreateView(CreateView):
    http_method_names = ["post"]
    form_class = UrlMappingCreateForm

    def form_valid(self, form):
        mapping = form.save()
        short_url = self.request.build_absolute_uri(f"/r/{mapping.key}/")
        return JsonResponse(
            {"short_url": short_url, "key": mapping.key, "url": mapping.url}, status=201
        )
