from django.contrib.sites.models import Site


def get_base_url():
    site = Site.objects.get_current()
    scheme = "https"
    base_url = f"{scheme}://{site.domain}"
    return base_url
