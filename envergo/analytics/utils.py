import binascii
import ipaddress
import logging
import socket
from datetime import timedelta

from _hashlib import pbkdf2_hmac
from django.conf import settings

from envergo.analytics.models import Event
from envergo.utils.urls import extract_mtm_params, update_qs

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

    try:
        ipaddress.ip_address(request_ip)
    except ValueError:
        return False

    # Find domain corresponding to ip
    socket.setdefaulttimeout(3)
    try:
        host = socket.gethostbyaddr(request_ip)[0]
    except OSError:
        return False

    logger.info("Request from ip %s, found matching domain %r", request_ip, host)

    # Does the request's domain matches a known bot domain?
    for bot_domain in bot_domains:
        if host.endswith(bot_domain):
            return True

    return False


def get_hash_unique_id(value: str):
    our_app_iters = 500_000
    salt_value = settings.HASH_SALT_KEY
    if not salt_value:
        logger.warning("Salt key not set")
    dk = pbkdf2_hmac(
        "sha256", str.encode(value), binascii.unhexlify(salt_value), our_app_iters
    )
    return dk.hex()


def log_event(category, event, request, **kwargs):
    visitor_id = request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")
    log_event_raw(category, event, visitor_id, request.user, request.site, **kwargs)


def log_event_raw(category, event, visitor_id, user, site, **kwargs):
    if visitor_id and not user.is_staff:
        unique_id = None
        if user.is_authenticated and user.access_haie:
            unique_id = get_hash_unique_id(user.email)
        Event.objects.create(
            category=category,
            event=event,
            session_key=visitor_id,
            unique_id=unique_id,
            metadata=kwargs,
            site=site,
        )


def set_visitor_id_cookie(response, value):
    """Set the unique visitor id cookie with correct lifetime.

    This visitor id is used for analytics purposes only and therefore does not require httponly.
    This way it can be read by the JS in frontend, e.g. for tracking when backend is down.
    """

    # CNIL's recommendation for tracking cookie lifetime = 13 months
    lifetime = timedelta(days=30 * 13)
    response.set_cookie(
        settings.VISITOR_COOKIE_NAME,
        value,
        max_age=lifetime.total_seconds(),
        domain=settings.SESSION_COOKIE_DOMAIN,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.SESSION_COOKIE_SECURE or None,
        httponly=False,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def extract_matomo_url_from_request(request):
    """Extract bare urls with matomo params from request."""
    bare_url = request.build_absolute_uri(request.path)
    return update_url_with_matomo_params(bare_url, request)


def update_url_with_matomo_params(url, request):
    """Add matomo params from request querystring to a given url."""

    current_url = request.build_absolute_uri()
    params = extract_mtm_params(current_url)
    is_edit = bool(request.GET.get("edit", False))
    if is_edit:
        params["edit"] = "true"
    is_alternative = bool(request.GET.get("alternative", False))
    if is_alternative:
        params["alternative"] = "true"

    return update_qs(url, params)


def get_matomo_tags(request):
    return {k: v for k, v in request.session.items() if k.startswith("mtm_")}


def get_user_type(user):
    """Return the type of user as a string depending on its attributes."""
    if not user or not user.is_authenticated:
        return "anonymous"
    if user.is_superuser or user.is_staff:
        return "administrator"
    elif user.is_instructor:
        return "instructor"
    else:
        return "guest"
