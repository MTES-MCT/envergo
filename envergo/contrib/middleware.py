import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)


class SetUrlConfBasedOnSite:
    """Depending on the served site, the urlconf will vary.
    We are not overriding settings.ROOT_URLCONF because settings should not be changed at runtime,
    it implies erratic behavior.
    By default, we use the Envergo Amenagement urlconf.
    If the site is the Haie site, we use the Envergo Haie urlconf.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.urlconf = "config.urls_amenagement"
        try:
            site = Site.objects.get_current(request)
        except Site.DoesNotExist:
            # If the site is not found, it might be from an invalid url or from and old
            # link lost somewhere in the wild.
            # We try to redirect to the amenagement site to mitigate the problem as
            # best as we can
            logger.error(
                f"Found url with bad domain in the wild: {request.get_host()}{request.get_full_path()}"
            )
            new_url = f"https://{settings.ENVERGO_AMENAGEMENT_DOMAIN}{request.get_full_path()}"
            return HttpResponseRedirect(new_url)

        request.site = site
        request.base_template = "amenagement/base.html"
        if site.domain == settings.ENVERGO_HAIE_DOMAIN:
            request.urlconf = "config.urls_haie"
            request.base_template = "haie/base.html"

        response = self.get_response(request)

        return response
