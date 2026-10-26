import uuid

from django.http import HttpResponseRedirect
from django.utils.http import escape_leading_slashes

from envergo.evaluations.models import (
    OBFUSCATION_KEY_PARAM,
    OBFUSCATION_KEYS_SESSION_KEY,
)


class MoveObfuscationKeyToSession:
    """Move an evaluation request's secret key from the url into the session.

    Rendered pages then never expose the key to scripts, referrers or logs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        has_key = OBFUSCATION_KEY_PARAM in request.GET
        for raw_key in request.GET.getlist(OBFUSCATION_KEY_PARAM):
            self.store_key(request, raw_key)

        # Any value, even empty or malformed, is dropped before a page renders.
        if has_key and request.method == "GET":
            response = HttpResponseRedirect(self.url_without_key(request))
        else:
            response = self.get_response(request)
        return response

    def store_key(self, request, raw_key):
        try:
            key = str(uuid.UUID(raw_key))
        except ValueError:
            return

        keys = request.session.get(OBFUSCATION_KEYS_SESSION_KEY, [])
        if key not in keys:
            request.session[OBFUSCATION_KEYS_SESSION_KEY] = keys + [key]

    def url_without_key(self, request):
        query = request.GET.copy()
        del query[OBFUSCATION_KEY_PARAM]

        # A path starting with "//" would redirect to another site.
        url = escape_leading_slashes(request.path)
        if query:
            url = f"{url}?{query.urlencode()}"
        return url
