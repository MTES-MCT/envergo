from django import forms
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from envergo.evaluations.models import Request
from envergo.evaluations.validators import application_number_validator


class EvaluationFormMixin(forms.Form):
    """Common code for all evaluation forms."""

    # We don't set `maxlength` to 15 because we want to allow copy-pasting
    # values with spaces
    application_number = forms.CharField(
        label=_("Application number"),
        help_text=_('A 15 chars value starting with "P"'),
        max_length=64,
    )

    def clean_application_number(self):
        dirty_number = self.cleaned_data.get("application_number")
        if dirty_number == "":
            return ""

        clean_number = dirty_number.replace(" ", "").strip().upper()
        application_number_validator(clean_number)
        return clean_number


class EvaluationSearchForm(EvaluationFormMixin, forms.Form):
    """Search for a single evaluation."""

    pass


class RequestForm(EvaluationFormMixin, forms.ModelForm):
    address = forms.CharField(
        label=_("What is your project's address?"),
        help_text=_("Type in a few characters to see suggestions"),
    )
    contact_email = forms.EmailField(label=_("Your e-mail address"))
    phone_number = PhoneNumberField(label=_("Your phone number"), required=False)
    other_contacts = forms.CharField(
        label=_("Other contacts data"),
        required=False,
        help_text=_(
            "Please let us know if we should warn others about the evaluation result."
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = Request
        fields = [
            "address",
            "application_number",
            "created_surface",
            "existing_surface",
            "contact_email",
            "phone_number",
            "other_contacts",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["application_number"].required = False
