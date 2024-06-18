import re

from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from envergo.evaluations.models import USER_TYPES, Request
from envergo.evaluations.validators import application_number_validator
from envergo.geodata.models import Department


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
            self.fields["contact_emails"].required = False

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
    department = forms.CharField(
        label="Department number",
        required=False,
    )
    postal_code = forms.CharField(
        label="Code postal de la commune",
        help_text="Si le projet se situe sur plusieurs communes indiquer le code postal de la commune principale",
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

            # override address with postal code if no address is provided
            postal_code = data.get("postal_code", None)
            if postal_code:
                data["address"] = postal_code
        else:
            # postal_code is not required if address is provided
            if "postal_code" in self._errors:
                del self._errors["postal_code"]

        # first try to get department from api-adresse.data.gouv.fr
        department_input = data.get("department", None)
        if not department_input:
            # Then try to export it from postal code
            postal_code = data.get("postal_code", None)
            if not postal_code:
                # then try to get it from the address which have not been picked up in the list
                # (it can be weirdly formatted)
                postal_code = self.extract_postal_code(data.get("address", ""))

            if postal_code:
                department_input = postal_code[:2]
                if department_input == "97":
                    # for overseas departments, we need the 3 first digits
                    department_input = postal_code[:3]

        department = (
            Department.objects.filter(department=department_input)
            .select_related("moulinette_config")
            .first()
        )
        if department and not department.is_activated():
            self.add_error(
                "department",
                ValidationError(
                    "Département non disponible", code="unavailable_department"
                ),
            )
            data["department"] = (
                department  # adding an error remove the department from cleaned_data, but we need it in the view
            )

        if not department:
            self.add_error(
                None,
                ValidationError(
                    "Nous ne parvenons pas à situer votre projet. Merci de vérifier votre saisie.",
                    code="unknown_department",
                ),
            )

        return data

    @staticmethod
    def extract_postal_code(address):
        # Regular expression pattern to match postal codes in the correct context
        postal_code_pattern = re.compile(r"\b\d{5}(?!\d)\b")
        matches = postal_code_pattern.findall(address)
        if matches:
            # Returning the last found postal code (in case of multiple matches)
            return matches[-1]
        return None


class WizardContactForm(EvaluationFormMixin, forms.ModelForm):
    user_type = forms.ChoiceField(
        label=mark_safe('<h2 class="fr-h6">Je suis :</h2>'),
        required=True,
        choices=USER_TYPES,
        initial=USER_TYPES.instructor,
        widget=forms.RadioSelect,
    )
    contact_emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Urbanism department email address(es)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
    )
    contact_phone = PhoneNumberField(
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
            Si vous décochez cette case, le porteur de projet
            ne recevra pas l'avis réglementaire.</span>
        <span class="if-unchecked">
            Si vous cochez cette case, et si le porteur de projet est concerné par une
            réglementation environnementale, EnvErgo lui enverra l'avis réglementaire.
            Vous serez en copie.
        </span>
        """,
    )

    class Meta:
        model = Request
        fields = [
            "user_type",
            "contact_emails",
            "contact_phone",
            "project_owner_emails",
            "project_owner_phone",
            "send_eval_to_project_owner",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact_emails"].widget.attrs["placeholder"] = _(
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
            "contact_emails",
            "contact_phone",
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
