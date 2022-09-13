from datetime import timedelta
from uuid import uuid4

from django.conf import settings

from config.settings.base import VISITOR_COOKIE_NAME


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
            request.COOKIES[VISITOR_COOKIE_NAME] = visitor_id

        response = self.get_response(request)

        if is_first_visit:
            # CNIL's recommendation for tracking cookie lifetime = 13 months
            lifetime = timedelta(days=30*13)
            response.set_cookie(
                settings.VISITOR_COOKIE_NAME,
                visitor_id,
                max_age=lifetime.total_seconds(),
                domain=settings.SESSION_COOKIE_DOMAIN,
                path=settings.SESSION_COOKIE_PATH,
                secure=settings.SESSION_COOKIE_SECURE or None,
                httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

        return response
