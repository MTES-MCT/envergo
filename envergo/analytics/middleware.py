from uuid import uuid4

from config.settings.base import VISITOR_COOKIE_NAME
from envergo.analytics.utils import (
    set_unsecure_visitor_id_cookie,
    set_visitor_id_cookie,
)


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
        is_first_visit = VISITOR_COOKIE_NAME not in request.COOKIES
        if is_first_visit:
            visitor_id = uuid4()
            request.COOKIES[VISITOR_COOKIE_NAME] = visitor_id
        else:
            visitor_id = request.COOKIES[VISITOR_COOKIE_NAME]

        response = self.get_response(request)

        if is_first_visit:
            set_visitor_id_cookie(response, visitor_id)

        unsecure_visitor_id_cookie_name = f"unsecure-{VISITOR_COOKIE_NAME}"
        is_unsecure_cookie_set = unsecure_visitor_id_cookie_name in request.COOKIES

        if (
            not is_unsecure_cookie_set
            or visitor_id != request.COOKIES[unsecure_visitor_id_cookie_name]
        ):
            set_unsecure_visitor_id_cookie(
                response, visitor_id, unsecure_visitor_id_cookie_name
            )

        return response


# Parameters that we want to store in session
MTM_PARAMETERS = (
    "mtm_campaign",
    "mtm_source",
    "mtm_medium",
    "mtm_kwd",
)


class StoreMtmValues:
    """Make sure the mtm values are stored until we need them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        GET_values = request.GET.copy()
        for key, val in GET_values.items():
            if key in MTM_PARAMETERS:
                request.session[key] = val

        response = self.get_response(request)
        return response
