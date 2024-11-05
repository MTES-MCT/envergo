from django.conf import settings
from django.contrib.sites.models import Site


class SetUrlConfBasedOnSite:
    """Depending on the served site, the urlconf will vary.
    We are not overriding settings.ROOT_URLCONF because settings should not be changed at runtime,
    it implies erratic behavior.
    By default, we use the EnvErgo Amenagement urlconf.
    If the site is the Haie site, we use the Envergo Haie urlconf.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.urlconf = "config.urls_amenagement"
        site = Site.objects.get_current(request)
        request.site = site
        request.base_template = "amenagement/base.html"
        if site.domain == settings.ENVERGO_HAIE_DOMAIN:
            request.urlconf = "config.urls_haie"
            request.base_template = "haie/base.html"

        response = self.get_response(request)

        return response
