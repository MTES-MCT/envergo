from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from envergo.evaluations.models import USER_TYPES, EvaluationVersion, Request
from envergo.evaluations.utils import extract_department_from_address
from envergo.evaluations.validators import application_number_validator
from envergo.geodata.models import Department
from envergo.utils.fields import MultipleFileField, NoIdnEmailField


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

        return super().full_clean()


REFERENCE_VALIDATOR = rf"^[A-Z0-9]{{{settings.ENVERGO_REFERENCE_LENGTH}}}$"


class EvaluationSearchForm(forms.Form):
    """Search for a single evaluation."""

    reference = forms.CharField(
        label=_("Envergo reference"),
        help_text=_("The value you received when you requested a regulatory notice."),
        max_length=64,
        validators=[RegexValidator(REFERENCE_VALIDATOR)],
    )


class WizardAddressForm(EvaluationFormMixin, forms.ModelForm):
    address = forms.CharField(
        label=_("Address of the project"),
        help_text=_("Type in a few characters to see suggestions"),
        error_messages={
            "required": """
                Ce champ est obligatoire. Si le projet n'a pas d'adresse précise,
                veuillez indiquer uniquement le code postal.
            """
        },
    )
    department = forms.CharField(
        label="Department number",
        required=False,
    )
    application_number = forms.CharField(
        label=_("Application number"),
        help_text=(
            "Si une demande de permis de construire ou d'aménager"
            " a déjà été déposée."
            "<br>"
            "<strong>Format :</strong> 15 caractères commençant par"
            " « PA », « PC »,"
            " « DP » ou « CU »."
        ),
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
        fields = ["address", "application_number", "project_description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["application_number"].required = False
        self.fields["application_number"].widget.attrs[
            "placeholder"
        ] = "PC0123456789012"
        self.fields["project_description"].widget.attrs["rows"] = 3

    def clean(self):
        data = super().clean()

        # first try to get department from api-adresse.data.gouv.fr
        address = data.get("address", "")
        department_input = data.get("department", None)
        if not department_input:
            # extract department from address
            department_input = extract_department_from_address(address)

        if department_input and department_input not in address:
            # when a town is selected on its own, without a complete address, there is no zip code.
            # We therefore add the department number
            data["address"] = f"{address} ({department_input})"

        department = Department.objects.filter(department=department_input).first()
        if department and not department.is_amenagement_activated():
            self.add_error(
                "department",
                ValidationError(
                    "Département non disponible", code="unavailable_department"
                ),
            )
            data["department"] = (
                department  # adding an error remove the department from cleaned_data, but we need it in the view
            )

        if not department and not self.has_error("address"):
            self.add_error(
                None,
                ValidationError(
                    "Nous ne parvenons pas à situer votre projet. "
                    "Merci de saisir quelques caractères et de sélectionner une option dans la liste.",
                    code="unknown_department",
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
        NoIdnEmailField(),
        label=_("Urbanism department email address(es)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=forms.EmailInput(attrs={"type": "email", "inputmode": "email"}),
    )
    urbanism_department_phone = PhoneNumberField(
        label=_("Urbanism department phone number"),
        region="FR",
        required=False,
    )
    project_owner_emails = SimpleArrayField(
        NoIdnEmailField(),
        label=_("Project sponsor email address(es)"),
        help_text=_("Petitioner, project manager…"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=forms.EmailInput(attrs={"type": "email", "inputmode": "email"}),
    )
    project_owner_phone = PhoneNumberField(
        label=_("Project sponsor phone number"),
        region="FR",
        required=False,
    )
    send_eval_to_project_owner = forms.BooleanField(
        label=_("Send evaluation to project sponsor"),
        initial=True,
        required=False,
        help_text="""
        <span class="if-checked">
            S’il est concerné par une réglementation environnementale, Envergo enverra l'avis réglementaire au porteur
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

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get("user_type")
        send_eval_to_project_owner = cleaned_data.get("send_eval_to_project_owner")

        # Remove project owner fields if the user does not want to send the evaluation to the project owner
        if not send_eval_to_project_owner and user_type == USER_TYPES.instructor:
            cleaned_data.pop("project_owner_emails", None)
            cleaned_data.pop("project_owner_phone", None)

        # Remove urbanism_department fields if the user is a petitioner
        if user_type == USER_TYPES.petitioner:
            cleaned_data.pop("urbanism_department_emails", None)
            cleaned_data.pop("urbanism_department_phone", None)

        return cleaned_data


class WizardFilesForm(forms.ModelForm):
    additional_files = MultipleFileField(
        label=_("Additional files you might deem useful for the evaluation"),
        required=False,
        help_text=f"""
            Formats autorisés : images (png, jpg), pdf, zip. <br>
            Maximum {settings.MAX_EVALREQ_FILES} fichiers. <br>
            Maximum {settings.MAX_EVALREQ_FILESIZE} Mo par fichier. <br>
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
        NoIdnEmailField(),
        label=_("Select your recipient(s) email address(es)"),
        help_text=_("Separate several addresses with a comma « , »"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=forms.EmailInput(attrs={"type": "email", "inputmode": "email"}),
    )


class EvaluationVersionForm(forms.ModelForm):
    class Meta:
        model = EvaluationVersion
        fields = ["message"]
