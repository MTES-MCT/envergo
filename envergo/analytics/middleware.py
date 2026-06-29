from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.http.response import HttpResponseRedirect

from envergo.analytics.utils import set_visitor_id_cookie


class SetVisitorIdCookie:
    """Make sure a unique visitor id cookie is always sent.

    By default, django does not set a session cookie for anonymous users.

    That is a problem because we want to log some events and associate
    them with a unique visitor session id.

    We could make sure to always create a session, but that would generate a db
    query for every single anonymous visit.

    Instead, we just set our own random visitor id as a cookie.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_first_visit = settings.VISITOR_COOKIE_NAME not in request.COOKIES
        visitor_id = None
        if is_first_visit:
            visitor_id = uuid4()
            request.COOKIES[settings.VISITOR_COOKIE_NAME] = visitor_id

        response = self.get_response(request)

        if is_first_visit:
            set_visitor_id_cookie(response, visitor_id)

        return response


# Parameters that we want to store in session
MTM_PARAMETERS = (
    "mtm_campaign",
    "mtm_source",
    "mtm_medium",
    "mtm_kwd",
)


class HandleMtmValues:
    """Store analytics data in session, then cleanup the url."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        GET_values = request.GET.copy()
        has_mtm_values = False
        for key in MTM_PARAMETERS:
            if key in GET_values:
                has_mtm_values = True
                value_list = GET_values.pop(key)
                if value_list:
                    value = value_list[0]
                    request.session[key] = value

        # Cleanup url from mtm_ values
        # We want those values to be displayed once, when the user clicks from the
        # original tracked link. However, we want to remove those values from the
        # subsequent pages. This is necessary since some views (moulinette views)
        # carry all GET parameters from one page to the other.
        response = None
        referer = request.META.get("HTTP_REFERER")
        if referer:
            referer_domain = urlparse(referer).netloc.split(":")[0]
            current_domain = request.get_host().split(":")[0]
            is_internal_req = referer_domain == current_domain
            if has_mtm_values and request.method == "GET" and is_internal_req:
                clean_url = f"{request.path}?{GET_values.urlencode()}"
                response = HttpResponseRedirect(clean_url)

        if response is None:
            response = self.get_response(request)

        return response
