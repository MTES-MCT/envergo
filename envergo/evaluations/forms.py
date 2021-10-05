from django import forms
from django.contrib.postgres.forms import SimpleArrayField
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


class EvaluationSearchForm(forms.Form):
    """Search for a single evaluation."""

    reference = forms.CharField(label=_("Reference"), max_length=64)


class RequestForm(EvaluationFormMixin, forms.ModelForm):
    address = forms.CharField(
        label=_("What is your project's address?"),
        help_text=_("Type in a few characters to see suggestions"),
    )
    created_surface = forms.IntegerField(
        label=_("Created surface"),
        help_text=_("Created_surface_help_text"),
        widget=forms.TextInput,
    )
    existing_surface = forms.IntegerField(
        label=_("Existing surface"),
        required=False,
        help_text=_("Existing surface help text"),
        widget=forms.TextInput,
    )
    application_number = forms.CharField(
        label=_("Application number"),
        help_text=_("If an application number was already submitted."),
        max_length=64,
    )

    contact_email = forms.EmailField(
        label=_("Urbanism department email"), help_text=_("Project instructor…")
    )
    project_sponsor_emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Project sponsor email address(es)"),
        help_text=_("Petitioner, project manager…"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
    )
    project_sponsor_phone_number = PhoneNumberField(
        label=_("Project sponsor phone number"), required=False, region="FR"
    )
    send_eval_to_sponsor = forms.BooleanField(
        label=_("Send evaluation to project sponsor"),
        initial=True,
        help_text=_(
            "If you uncheck this box, you will be the only recipient of the evaluation."
        ),
    )

    class Meta:
        model = Request
        fields = [
            "address",
            "application_number",
            "created_surface",
            "existing_surface",
            "contact_email",
            "project_sponsor_emails",
            "project_sponsor_phone_number",
            "send_eval_to_sponsor",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["created_surface"].widget.attrs["placeholder"] = _(
            "In square meters"
        )
        self.fields["existing_surface"].widget.attrs["placeholder"] = _(
            "In square meters"
        )
        self.fields["project_sponsor_emails"].widget.attrs["placeholder"] = _(
            "Provide one or several addresses separated by commas « , »"
        )
        self.fields["application_number"].required = False
        self.fields["application_number"].widget.attrs["placeholder"] = _(
            'A 15 chars value starting with "P"'
        )
