from django.contrib.sites.models import Site


class SetUrlConfBasedOnSite:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.urlconf = "config.urls_amenagement"
        try:
            site = Site.objects.get_current(request)
            if site.name == "Haie":
                request.urlconf = "config.urls_haie"
        except Site.DoesNotExist:
            pass  # No site found, use default ROOT_URLCONF (e.g. for tests)

        response = self.get_response(request)

        return response
