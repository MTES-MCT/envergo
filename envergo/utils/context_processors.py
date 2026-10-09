from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from envergo.users.forms import NewsletterOptInForm

# Crisp breaks those pages
CHATBOX_BLACKLIST = ["demo_catchment_area", "input_hedges"]


def settings_context(_request):
    """Settings available by default to the templates context."""
    # Note: we intentionally do NOT expose the entire settings
    # to prevent accidental leaking of sensitive information

    # resolver_match is None on error pages, whose path matched no view
    resolver_match = _request.resolver_match
    view_name = resolver_match.view_name if resolver_match else None
    if view_name in CHATBOX_BLACKLIST:
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
        "SENTRY_KEY": settings.SENTRY_KEY,
        "ENV_NAME": settings.ENV_NAME,
        "CRISP_CHATBOX_ENABLED": chatbox_enabled,
        "CRISP_WEBSITE_ID": crisp_website_id,
        "HAIE_FAQ_URLS": settings.HAIE_FAQ_URLS,
        "DISPLAY_TEACHING_TOPBAR": settings.DISPLAY_TEACHING_TOPBAR,
    }


def multi_sites_context(_request):
    """Give some useful context to handle multi sites"""
    # _request.base_template has been populated by a middleware
    return {
        "base_template": _request.base_template,
        "contact_url": f"{reverse("contact_us")}"
        f"{settings.CONTACT_TEAM_ANCHOR if _request.site.domain == settings.ENVERGO_HAIE_DOMAIN else ''}",
        "contact_guh_anchor": settings.CONTACT_GUH_ANCHOR,
        "preview_image_url": (
            _request.build_absolute_uri(static("images/preview_haie.png"))
            if _request.site.domain == settings.ENVERGO_HAIE_DOMAIN
            else None
        ),
    }


def newsletter_context(_request):
    return {
        "newsletter_opt_in_form": NewsletterOptInForm(),
    }
