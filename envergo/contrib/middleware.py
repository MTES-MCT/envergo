from django.contrib.sites.models import Site

from envergo.geodata.utils import is_test


class SetUrlConfBasedOnSite:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.urlconf = "config.urls_amenagement"
        try:
            site = Site.objects.get_current(request)
            request.site = site
            if site.name == "Haie":
                request.urlconf = "config.urls_haie"
        except Site.DoesNotExist as e:
            if is_test():
                pass
            else:
                raise e

        response = self.get_response(request)

        return response