from django.contrib.sites.models import Site


def get_base_url(site_id):
    site = Site.objects.get(id=site_id)
    scheme = "https"
    base_url = f"{scheme}://{site.domain}"
    return base_url
