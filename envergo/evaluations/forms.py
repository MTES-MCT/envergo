from django import forms
from django.utils.translation import ugettext_lazy as _


class EvaluationSearchForm(forms.Form):
    """Search for a single evaluation."""

    application_number = forms.CharField(
        label=_("Application number"),
        help_text=_('A 15 chars value starting with "P"'),
        widget=forms.TextInput(attrs={"placeholder": "PC04412621D1029"}),
        max_length=15,
    )
