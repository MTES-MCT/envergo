import re
from urllib.parse import urlparse

from django.conf import settings
from django.urls import Resolver404, resolve

from envergo.urlmappings.models import UrlMapping


def unfold_url(url):
    """Return the url corresponding to the given short url.

    If the given url is not a valid short url, returns the original url.
    """
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # pragma: allowlist secret
    length = settings.URLMAPPING_KEY_LENGTH
    pattern = rf"(?P<key>[{alphabet}]{{{length}}})/$"
    res = re.search(pattern, url)

    if res:
        key = res.group("key")
        try:
            mapping = UrlMapping.objects.get(key=key)
            url = mapping.url
        except UrlMapping.DoesNotExist:
            pass
    return url


def resolve_consultation_url(url):
    """If `url` is a petition project consultation url, return the url of that project's initial simulation instead.

    If it is not a petition project consultation url, or if we cant resolve the project url, it returns the given url.
    """
    url = unfold_url(url)
    path = urlparse(url).path
    try:
        match = resolve(path, urlconf="config.urls_haie")
    except Resolver404:
        return url

    if match.url_name != "petition_project":
        return url

    from envergo.petitions.models import PetitionProject

    try:
        project = PetitionProject.objects.get(reference=match.kwargs["reference"])
    except PetitionProject.DoesNotExist:
        return url

    initial_simulation = project.simulations.filter(is_initial=True).first()
    return initial_simulation.moulinette_url if initial_simulation else url
