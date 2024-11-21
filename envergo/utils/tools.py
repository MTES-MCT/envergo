from typing import Literal

from django.conf import settings
from django.contrib.sites.models import Site


def get_base_url(site_domain):
    scheme = "https"
    base_url = f"{scheme}://{site_domain}"
    return base_url


def get_site_literal(site: Site) -> Literal["haie", "amenagement"]:
    if site.domain == settings.ENVERGO_HAIE_DOMAIN:
        return "haie"

    return "amenagement"
