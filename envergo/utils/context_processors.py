from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import NoReverseMatch, reverse


def settings_context(_request):
    """Settings available by default to the templates context."""
    # Note: we intentionally do NOT expose the entire settings
    # to prevent accidental leaking of sensitive information

    # We disable the chatbox on the catchment area page
    # Because it breaks the map, for reasons I just don't understand
    try:
        catchment_area_page_url = reverse("2150_debug")
    except NoReverseMatch:
        catchment_area_page_url = None

    if _request.path == catchment_area_page_url:
        chatbox_enabled = False
    else:
        chatbox_enabled = settings.CRISP_CHATBOX_ENABLED

    return {
        "DEBUG": settings.DEBUG,
        "ANALYTICS": settings.ANALYTICS,
        "SENTRY_DSN": settings.SENTRY_DSN,
        "ENV_NAME": settings.ENV_NAME,
        "CRISP_CHATBOX_ENABLED": chatbox_enabled,
        "CRISP_WEBSITE_ID": settings.CRISP_WEBSITE_ID,
    }


def multi_sites_context(_request):
    """Give some useful context to handle multi sites"""
    current_site = get_current_site(_request)
    base_template = "base.html"
    if current_site.name == "Haie":
        base_template = "haie/base.html"
    return {
        "current_site_id": current_site.id,
        "base_template": base_template,
    }
