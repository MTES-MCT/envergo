from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from envergo.evaluations.models import USER_TYPES, Request
from envergo.evaluations.validators import application_number_validator


class EvaluationFormMixin(forms.Form):
    """Common code for all evaluation forms."""

    def clean_application_number(self):
        dirty_number = self.cleaned_data.get("application_number")
        if dirty_number == "":
            return ""

        clean_number = dirty_number.replace(" ", "").strip().upper()
        application_number_validator(clean_number)
        return clean_number

    def clean_project_owner_phone(self):
        phone = self.cleaned_data["project_owner_phone"]
        return str(phone)

    def full_clean(self):
        """Update validation rules depending on user type.

        Depending on the user type (instructor or petitioner), some fields are required or not.
        """
        data = self.data
        user_type = data.get("user_type", None)

        if user_type == USER_TYPES.petitioner:
            self.fields["urbanism_department_emails"].required = False

        if user_type == USER_TYPES.instructor:
            send_eval_to_project_owner = data.get("send_eval_to_project_owner", False)
            if not send_eval_to_project_owner:
                self.fields["project_owner_emails"].required = False
                self.fields["project_owner_phone"].required = False

        return super().full_clean()


REFERENCE_VALIDATOR = rf"^[A-Z0-9]{{{settings.ENVERGO_REFERENCE_LENGTH}}}$"


class EvaluationSearchForm(forms.Form):
    """Search for a single evaluation."""

    reference = forms.CharField(
        label=_("EnvErgo reference"),
        help_text=_("The value you received when you requested a regulatory notice."),
        max_length=64,
        validators=[RegexValidator(REFERENCE_VALIDATOR)],
    )


class WizardAddressForm(EvaluationFormMixin, forms.ModelForm):
    address = forms.CharField(
        label=_("What is the project's address?"),
        help_text=_("Type in a few characters to see suggestions"),
        error_messages={
            "required": """
                Ce champ est obligatoire. Si le projet n'a pas d'adresse,
                cochez la case ci-dessous.
            """
        },
    )
    no_address = forms.BooleanField(
        label=_("This project is not linked to an address"),
        required=False,
    )
    application_number = forms.CharField(
        label=_("Application number"),
        help_text=_("If an application number was already submitted."),
        max_length=64,
    )
    project_description = forms.CharField(
        label=_("Project description, comments"),
        required=False,
        widget=forms.Textarea,
        help_text="""
            <a class="fr-link" aria-describedby="tooltip-project-description" href="#" onclick="return false">
                Précautions liées au contenu
            </a>
            <span class="fr-tooltip fr-placement" id="tooltip-project-description" role="tooltip" aria-hidden="true">
                Merci de ne fournir que les informations utiles à la compréhension de la demande d’avis.<br />
                Attention à ne pas mentionner de propos diffamatoires ou d’informations sensibles
                (opinions philosophiques, syndicales, politiques, religieuses, données de santé…).
            </span>
        """,
    )

    class Meta:
        model = Request
        fields = ["address", "no_address", "application_number", "project_description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["application_number"].required = False
        self.fields["application_number"].widget.attrs["placeholder"] = _(
            "15 caractères commençant par « PA », « PC », « DP » ou « CU »"
        )
        self.fields["project_description"].widget.attrs["rows"] = 3

    def clean(self):
        data = super().clean()
        no_address = data.get("no_address", False)
        if no_address:
            self.fields["address"].required = False
            if "address" in self._errors:
                del self._errors["address"]

            address = data.get("address", None)
            if address:
                self.add_error(
                    "no_address",
                    _(
                        "You checked this box but still provided an address. Please check your submission."
                    ),
                )

        return data


class WizardContactForm(EvaluationFormMixin, forms.ModelForm):
    user_type = forms.ChoiceField(
        label=mark_safe('<h2 class="fr-h6">Je suis :</h2>'),
        required=True,
        choices=USER_TYPES,
        initial=USER_TYPES.instructor,
        widget=forms.RadioSelect,
    )
    urbanism_department_emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Urbanism department email address(es)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
    )
    urbanism_department_phone = PhoneNumberField(
        label=_("Urbanism department phone number"),
        region="FR",
        required=False,
    )
    project_owner_emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Project sponsor email address(es)"),
        help_text=_("Petitioner, project manager…"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
    )
    project_owner_phone = PhoneNumberField(
        label=_("Project sponsor phone number"), region="FR"
    )
    send_eval_to_project_owner = forms.BooleanField(
        label=_("Send evaluation to project sponsor"),
        initial=True,
        required=False,
        help_text="""
        <span class="if-checked">
            S’il est concerné par une réglementation environnementale, EnvErgo enverra l'avis réglementaire au porteur
            de projet et l’accompagnera dans la compréhension de ses obligations. Vous serez en copie de l’avis.
        </span>
        <span class="if-unchecked">
            Le porteur de projet ne recevra pas l'avis réglementaire. Il pourrait alors manquer à ses obligations au
            titre de la réglementation environnementale.
        </span>
        """,
    )

    class Meta:
        model = Request
        fields = [
            "user_type",
            "urbanism_department_emails",
            "urbanism_department_phone",
            "project_owner_emails",
            "project_owner_phone",
            "send_eval_to_project_owner",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["urbanism_department_emails"].widget.attrs["placeholder"] = _(
            "Provide one or several addresses separated by commas « , »"
        )
        self.fields["project_owner_emails"].widget.attrs["placeholder"] = _(
            "Provide one or several addresses separated by commas « , »"
        )


# See https://docs.djangoproject.com/en/4.2/topics/http/file-uploads/#uploading-multiple-files
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class WizardFilesForm(forms.ModelForm):
    additional_files = MultipleFileField(
        label=_("Additional files you might deem useful for the evaluation"),
        required=False,
        help_text=f"""
            Formats autorisés : images (png, jpg), pdf, zip. <br>
            Maximum {settings.MAX_EVALREQ_FILES} fichiers. <br>
            Maximum 20 Mo par fichier. <br>
        """,
    )

    class Meta:
        model = Request
        fields = ["additional_files"]


class RequestForm(WizardAddressForm, WizardContactForm):
    class Meta:
        model = Request
        fields = [
            "address",
            "application_number",
            "project_description",
            "user_type",
            "urbanism_department_emails",
            "urbanism_department_phone",
            "project_owner_emails",
            "project_owner_phone",
            "send_eval_to_project_owner",
        ]


class EvaluationShareForm(forms.Form):
    emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Select your recipient(s) email address(es)"),
        help_text=_("Separate several addresses with a comma « , »"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
    )
