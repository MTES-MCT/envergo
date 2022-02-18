from django import forms
from django.contrib.gis.forms.fields import PointField
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
    )
    coords = PointField(label=_("Coordinates"), required=True, srid=4326)
