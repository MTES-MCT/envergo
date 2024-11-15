from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView, TemplateView

from envergo.pages.views import (
    HomeHaieView,
    LegalMentionsView,
    Outlinks,
    PrivacyView,
    TermsOfServiceView,
)

urlpatterns = [
    path("", HomeHaieView.as_view(), name="home"),
    path(_("legal-mentions/"), LegalMentionsView.as_view(), name="legal_mentions"),
    path(_("tos/"), TermsOfServiceView.as_view(), name="terms_of_service"),
    path(_("privacy/"), PrivacyView.as_view(), name="privacy"),
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
