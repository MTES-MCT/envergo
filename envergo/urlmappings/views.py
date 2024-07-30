from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, RedirectView
from django.views.generic.detail import SingleObjectMixin
from django_ratelimit.decorators import ratelimit

from envergo.urlmappings.forms import UrlMappingCreateForm
from envergo.urlmappings.models import UrlMapping


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST"), name="post")
class UrlMappingCreateView(CreateView):
    http_method_names = ["post"]
    form_class = UrlMappingCreateForm

    def form_valid(self, form):
        mapping = form.save()
        short_url = reverse("urlmapping_redirect", kwargs={"key": mapping.key})
        full_short_url = self.request.build_absolute_uri(short_url)
        return JsonResponse(
            {"short_url": full_short_url, "key": mapping.key, "url": mapping.url},
            status=201,
        )

    def form_invalid(self, form):
        return JsonResponse(
            {"message": "Cannot create mapping", "errors": form.errors}, status=400
        )


class UrlMappingRedirect(SingleObjectMixin, RedirectView):
    """Redirect short url to original url."""

    model = UrlMapping
    slug_field = "key"
    slug_url_kwarg = "key"

    def get_redirect_url(self, *args, **kwargs):
        mapping = self.get_object()
        return mapping.url
