from django import forms
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.validators import application_number_validator


class EvaluationFormMixin(forms.Form):
    """Common code for all evaluation forms."""

    # We don't set `maxlength` to 15 because we want to allow copy-pasting
    # values with spaces
    application_number = forms.CharField(
        label=_("Application number"),
        help_text=_('A 15 chars value starting with "P"'),
        widget=forms.TextInput(attrs={"placeholder": "PC04412621D1029"}),
        validators=[application_number_validator],
        max_length=64,
    )

    def clean_application_number(self):
        dirty_number = self.cleaned_data.get("application_number")
        return dirty_number.replace(" ", "").strip().upper()


class EvaluationSearchForm(EvaluationFormMixin, forms.Form):
    """Search for a single evaluation."""

    pass
