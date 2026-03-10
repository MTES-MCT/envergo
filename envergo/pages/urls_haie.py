from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView

from envergo.moulinette.views import ConfigHaieSettingsView
from envergo.pages.models import HaieSitemap
from envergo.pages.views import HomeHaieView, Outlinks

sitemaps = {"static_pages": HaieSitemap}


# Exclude staging envs from search engine results
if settings.ENV_NAME == "production":
    robots_file = "haie/robots.txt"
else:
    robots_file = "robots_staging.txt"


urlpatterns = [
    path("", HomeHaieView.as_view(), name="home"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name=robots_file, content_type="text/plain"),
    ),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        _("legal-mentions/"),
        TemplateView.as_view(template_name="haie/pages/legal_mentions.html"),
        name="legal_mentions",
    ),
    path(
        _("privacy/"),
        TemplateView.as_view(template_name="haie/pages/privacy.html"),
        name="privacy",
    ),
    path(
        "stats/",
        RedirectView.as_view(url="https://sites.google.com/view/stats-envergo/"),
        name="stats",
    ),
    path(
        _("accessibility/"),
        TemplateView.as_view(template_name="pages/accessibility.html"),
        name="accessibility",
    ),
    path(
        _("contact-us/"),
        TemplateView.as_view(template_name="haie/pages/contact_us.html"),
        name="contact_us",
    ),
    path("admin/outlinks/", Outlinks.as_view(), name="outlinks"),
    path(
        "parametrage/<str:department>/",
        ConfigHaieSettingsView.as_view(),
        name="confighaie_settings",
    ),
    path(
        "parametrage/<str:department>/<str:date_slug>/",
        ConfigHaieSettingsView.as_view(),
        name="confighaie_detail",
    ),
]
