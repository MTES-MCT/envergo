from django.conf import settings
from django.contrib.sites.models import Site


class SetUrlConfBasedOnSite:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        site = Site.objects.get_current()
        if site.name == "Haie":
            settings.ROOT_URLCONF = "config.urls_haie"
        else:
            settings.ROOT_URLCONF = "config.urls_envergo"

        response = self.get_response(request)

        return response
