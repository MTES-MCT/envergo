from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from envergo.urlmappings.models import UrlMapping


class UrlMappingCreateForm(forms.ModelForm):
    """Form for creating a short URL mapping.

    Only URLs pointing to one of our own domains (amenagement or haie) are
    accepted, so the shortener cannot be abused as an open redirect.
    """

    class Meta:
        fields = ["url"]
        model = UrlMapping

    def clean_url(self):
        """Reject URLs whose hostname is not one of our own domains.

        Using urlparse().hostname (rather than substring matching on the raw
        URL) ensures lookalike domains, subdomains, and URLs that embed an
        allowed domain in their path or userinfo cannot bypass the check.
        """
        url = self.cleaned_data["url"]
        hostname = urlparse(url).hostname
        allowed_domains = {
            settings.ENVERGO_AMENAGEMENT_DOMAIN,
            settings.ENVERGO_HAIE_DOMAIN,
        }
        if hostname not in allowed_domains:
            raise forms.ValidationError("Cette URL n'est pas autorisée.")

        return url
