from django import forms

from envergo.urlmappings.models import UrlMapping


class UrlMappingCreateForm(forms.ModelForm):
    class Meta:
        fields = ["url"]
        model = UrlMapping
