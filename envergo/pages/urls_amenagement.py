from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView

from envergo.geodata.views import ParcelsExport
from envergo.pages.models import AmenagementSitemap
from envergo.pages.views import (
    AvailabilityInfo,
    DebugView,
    GeometriciansView,
    HomeAmenagementView,
    NewsFeed,
    NewsView,
    Outlinks,
    TermsOfServiceView,
)

sitemaps = {"static_pages": AmenagementSitemap}


# Exclude staging envs from search engine results
if settings.ENV_NAME == "production":
    robots_file = "amenagement/robots.txt"
else:
    robots_file = "robots_staging.txt"


urlpatterns = [
    path("", HomeAmenagementView.as_view(), name="home"),
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
        TemplateView.as_view(template_name="amenagement/pages/legal_mentions.html"),
        name="legal_mentions",
    ),
    path(_("tos/"), TermsOfServiceView.as_view(), name="terms_of_service"),
    path(
        _("privacy/"),
        TemplateView.as_view(template_name="amenagement/pages/privacy.html"),
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
        TemplateView.as_view(template_name="amenagement/pages/contact_us.html"),
        name="contact_us",
    ),
    path(
        _("faq/"),
        include(
            [
                path(
                    "",
                    TemplateView.as_view(template_name="pages/faq/index.html"),
                    name="faq",
                ),
                path(
                    _("loi-sur-leau/"),
                    TemplateView.as_view(template_name="pages/faq/loi_sur_leau.html"),
                    name="faq_loi_sur_leau",
                ),
                path(
                    _("natura-2000/"),
                    TemplateView.as_view(template_name="pages/faq/natura_2000.html"),
                    name="faq_natura_2000",
                ),
                path(
                    _("eval-env/"),
                    TemplateView.as_view(template_name="pages/faq/eval_env.html"),
                    name="faq_eval_env",
                ),
                path(
                    _("envergo-news/"),
                    NewsView.as_view(),
                    name="faq_news",
                ),
                path(
                    _("envergo-news/feed/"),
                    NewsFeed(),
                    name="news_feed",
                ),
                path(
                    _("available-departments/"),
                    AvailabilityInfo.as_view(),
                    name="faq_availability_info",
                ),
                path(
                    "debug/",
                    DebugView.as_view(),
                    name="debug_to_be_deleted",
                ),
            ]
        ),
    ),
    path(
        _("map/"),
        TemplateView.as_view(template_name="pages/map.html"),
        name="map",
    ),
    path(
        _("parcels.geojson"),
        ParcelsExport.as_view(),
        name="parcels_export",
    ),
    path("admin/outlinks/", Outlinks.as_view(), name="outlinks"),
    path(_("géomètres/"), RedirectView.as_view(url="/geometres/")),
    path(_("geometres/"), GeometriciansView.as_view(), name="geometricians"),
]
