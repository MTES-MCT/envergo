import logging
import socket
from datetime import timedelta

from django.conf import settings

from envergo.analytics.models import Event

logger = logging.getLogger(__name__)


def is_request_from_a_bot(request):
    """Check that the requests comes certain domains identified as bots.

    We perform a reverse dns lookup of the user agent ip, and compare it
    against known domain origin for bots.

    """

    bot_domains = [
        "googlebot.com",
        "search.msn.com",
        "search.qwant.com",
        "amazonaws.com",  # Trello preview bot, among others
        "vultrusercontent.com",  # Updown.io
        "compute.outscale.com",  # Mattermost
    ]

    request_ip = request.META.get("HTTP_X_REAL_IP", None)
    if request_ip is None:
        return False

    # Find domain corresponding to ip
    socket.setdefaulttimeout(3)
    try:
        host = socket.gethostbyaddr(request_ip)[0]
    except OSError:
        return False

    logger.info(f"Request from ip {request_ip}, found matching domain {host}")

    # Does the request's domain matches a known bot domain?
    for bot_domain in bot_domains:
        if host.endswith(bot_domain):
            return True

    return False


def log_event(category, event, request, **kwargs):

    visitor_id = request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")

    if visitor_id:
        Event.objects.create(
            category=category, event=event, session_key=visitor_id, metadata=kwargs
        )


def set_visitor_id_cookie(response, value):
    """Set the unique visitor id cookie with correct lifetime."""

    # CNIL's recommendation for tracking cookie lifetime = 13 months
    lifetime = timedelta(days=30 * 13)
    response.set_cookie(
        settings.VISITOR_COOKIE_NAME,
        value,
        max_age=lifetime.total_seconds(),
        domain=settings.SESSION_COOKIE_DOMAIN,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.SESSION_COOKIE_SECURE or None,
        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
