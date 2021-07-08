from django.urls import path
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        _("legal-mentions/"),
        TemplateView.as_view(template_name="pages/legal_mentions.html"),
        name="legal_mentions",
    ),
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
]
