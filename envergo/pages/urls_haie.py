from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView

from envergo.pages.views import HomeHaieView, Outlinks

urlpatterns = [
    path("", HomeHaieView.as_view(), name="home"),
    path(
        _("legal-mentions/"),
        TemplateView.as_view(template_name="haie/pages/legal_mentions.html"),
        name="legal_mentions",
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
]
