from django import forms
from django.utils.translation import gettext_lazy as _


class MoulinetteForm(forms.Form):
    created_surface = forms.IntegerField(
        label=_("Created surface"), required=True, help_text=_("In square meters")
    )
    existing_surface = forms.IntegerField(
        label=_("Existing surface"), required=True, help_text=_("In square meters")
    )
    address = forms.CharField(
        label=_("Search for the address to center the map"),
        help_text=_("Type in a few characters to see suggestions"),
        required=False,
    )
    lng = forms.DecimalField(
        label=_("Longitude"), required=True, max_digits=9, decimal_places=6
    )
    lat = forms.DecimalField(
        label=_("Latitude"), required=True, max_digits=9, decimal_places=6
    )
