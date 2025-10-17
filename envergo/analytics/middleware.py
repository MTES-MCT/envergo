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
        else:
            # these part of the code can be removed 13 months after the release (2026-06-01)
            self.remove_http_only_on_visitor_id_cookie(request, response)

        return response

    def remove_http_only_on_visitor_id_cookie(self, request, response):
        """Remove the httpOnly flag on the visitor id cookie.

        This is a temporary fix to allow the frontend to read the visitor id cookie.
        But it should be removed because it makes the cookie lifetime infinite

        It does not set the cookie again, if it has already been set by another middleware/view
        """
        if not response.cookies.get(settings.VISITOR_COOKIE_NAME):
            response.delete_cookie(settings.VISITOR_COOKIE_NAME)
            set_visitor_id_cookie(
                response, request.COOKIES[settings.VISITOR_COOKIE_NAME]
            )


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

        if has_mtm_values and request.method == "GET":
            clean_url = f"{request.path}?{GET_values.urlencode()}"
            response = HttpResponseRedirect(clean_url)
        else:
            response = self.get_response(request)

        return response
