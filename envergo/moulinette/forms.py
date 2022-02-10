from django import forms
from django.utils.translation import gettext_lazy as _


class MoulinetteForm(forms.Form):
    created_surface = forms.IntegerField(
        label=_("Created surface"), required=True, help_text=_("In square meters")
    )
    existing_surface = forms.IntegerField(
        label=_("Existing surface"), required=True, help_text=_("In square meters")
    )
    project_footprint = forms.JSONField(label=_("Project footprint"), required=True)
