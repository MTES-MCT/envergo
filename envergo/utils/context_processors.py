from django.conf import settings
from django.urls import NoReverseMatch, reverse

from envergo.users.forms import NewsletterOptInForm


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
        chatbox_enabled = (
            settings.CRISP["HAIE"]["CHATBOX_ENABLED"]
            if _request.site.domain == settings.ENVERGO_HAIE_DOMAIN
            else settings.CRISP["AMENAGEMENT"]["CHATBOX_ENABLED"]
        )

    analytics = (
        settings.ANALYTICS["HAIE"]
        if _request.site.domain == settings.ENVERGO_HAIE_DOMAIN
        else settings.ANALYTICS["AMENAGEMENT"]
    )

    crisp_website_id = (
        settings.CRISP["HAIE"]["WEBSITE_ID"]
        if _request.site.domain == settings.ENVERGO_HAIE_DOMAIN
        else settings.CRISP["AMENAGEMENT"]["WEBSITE_ID"]
    )

    return {
        "DEBUG": settings.DEBUG,
        "ANALYTICS": analytics,
        "SENTRY_DSN": settings.SENTRY_DSN,
        "ENV_NAME": settings.ENV_NAME,
        "CRISP_CHATBOX_ENABLED": chatbox_enabled,
        "CRISP_WEBSITE_ID": crisp_website_id,
    }


def multi_sites_context(_request):
    """Give some useful context to handle multi sites"""
    # _request.base_template has been populated by a middleware
    return {
        "base_template": _request.base_template,
    }


def newsletter_context(_request):
    return {
        "newsletter_opt_in_form": NewsletterOptInForm(),
    }
