import re

from django.conf import settings

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
