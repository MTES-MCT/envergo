from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView

from envergo.geodata.views import ParcelsExport
from envergo.pages.views import LegalMentionsView, Outlinks

urlpatterns = [
    path(
        "",
        RedirectView.as_view(pattern_name="moulinette_home", query_string=True),
        name="home",
    ),
    path(_("stats/"), include("envergo.stats.urls")),
    path(_("legal-mentions/"), LegalMentionsView.as_view(), name="legal_mentions"),
    path(
        _("accessibility/"),
        TemplateView.as_view(template_name="pages/accessibility.html"),
        name="accessibility",
    ),
    path(
        _("contact-us/"),
        TemplateView.as_view(template_name="pages/contact_us.html"),
        name="contact_us",
    ),
    path(
        _("faq/"),
        include(
            [
                path("", TemplateView.as_view(template_name="pages/faq/index.html"), name="faq"),
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
]
