from datetime import timedelta
from textwrap import dedent

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms.fields import FileField
from django.utils import timezone
from django.utils.formats import date_format

from envergo.moulinette.utils import MoulinetteUrl
from envergo.petitions.models import (
    DECISIONS,
    FORBIDDEN_STAGE_TRANSITIONS,
    PetitionProject,
    Simulation,
    StatusLog,
)
from envergo.utils.fields import ProjectStageField
from envergo.utils.urls import remove_from_qs
from envergo.utils.validators import validate_mime


class PetitionProjectForm(forms.ModelForm):
    """Form for creating a petition project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moulinette_url"].required = True
        self.fields["_category"].required = True

    def clean_moulinette_url(self):
        """Remove the date parameter from the moulinette url if there is one

        We keep the date during simulations because it can be used for project alternatives or for simulations at a
        given point in time. However, when creating a file, we want to take current legislation into account, so we
        remove the date if necessary.
        """
        moulinette_url = self.cleaned_data["moulinette_url"]
        cleaned_moulinette_url = remove_from_qs(moulinette_url, "date")
        return cleaned_moulinette_url

    class Meta:
        model = PetitionProject
        fields = [
            "moulinette_url",
            "_category",
        ]


class PetitionProjectInstructorEspecesProtegeesForm(forms.ModelForm):
    """Form for adding instructor fields to a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "onagre_number",
        ]
        widgets = {
            "onagre_number": forms.TextInput(
                attrs={"placeholder": "AAAA-MM-XXX-NNNNN"}
            ),
        }


class PetitionProjectInstructorNotesForm(forms.ModelForm):
    """Form for adding instructor fields to a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "instructor_free_mention",
            "instructor_private_mention",
        ]
        widgets = {
            "instructor_free_mention": forms.Textarea(
                attrs={
                    "rows": 15,
                    "placeholder": "Ajoutez vos notes ici…",
                },
            ),
            "instructor_private_mention": forms.Textarea(
                attrs={
                    "rows": 15,
                    "placeholder": "Ajoutez vos notes privées ici…",
                },
            ),
        }
        labels = {
            "instructor_free_mention": "Notes pour tous les services consultés",
            "instructor_private_mention": "Notes internes au service coordonnateur",
        }
        help_texts = {
            "instructor_free_mention": (
                "Partagez ici tout ce qui est utile à la collaboration"
                " entre services instructeurs."
            ),
            "instructor_private_mention": (
                "Partagez ici tout ce qui est utile à votre suivi de la demande."
                " Les services consultés n'ont pas accès à ces notes."
            ),
        }


def validate_file_size(value):
    size_limit = 20 * 1024 * 1024  # 20 mb
    if value.size > size_limit:
        raise ValidationError(
            "Le message n'a pas pu être envoyé car la pièce jointe dépasse la taille maximale autorisée de 20 Mo."
        )


validate_extension = FileExtensionValidator(
    allowed_extensions=["png", "jpg", "jpeg", "pdf", "zip"],
)

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "application/pdf",
    "application/zip",
}


def validate_mime_type(value):
    validate_mime(value, ALLOWED_MIME_TYPES)


class PetitionProjectInstructorMessageForm(forms.Form):
    """Form to send a message through Démarche numérique API."""

    message_body = forms.CharField(
        label="Message",
        help_text="",
        widget=forms.Textarea(
            attrs={"rows": 8, "placeholder": "Écrivez votre message ici…"}
        ),
    )

    additional_file = FileField(
        label="Pièce jointe",
        required=False,
        help_text="""Une seule pièce jointe est autorisée par message.<br>
            Formats autorisés : images (png, jpg), pdf, zip.<br>
            Taille maximale autorisée : 20 Mo.
        """,
        validators=[validate_file_size, validate_extension, validate_mime_type],
    )

    class Meta:
        fields = ["message_body", "additional_file"]


# Closing requirements matrix: for each final decision, the set of closing
# fields the instructor must provide. See StateChangeForm docstring for the
# rationale behind each requirement. Decisions absent from this mapping
# (i.e. "unset") cannot close a dossier.
CLOSING_FIELD_REQUIREMENTS = {
    DECISIONS.tacit_agreement: {"simulation_check", "applicant_message"},
    DECISIONS.express_agreement: {
        "simulation_check",
        "prefectural_order",
        "applicant_message",
    },
    DECISIONS.opposition: {
        "simulation_check",
        "prefectural_order",
        "applicant_message",
    },
    DECISIONS.dropped: {"applicant_message"},
}

# Error (code, message) raised when a required closing field is missing.
CLOSING_FIELD_ERRORS = {
    "simulation_check": (
        "simulation_not_checked",
        "Pour garantir la qualité des données transmises à l'observatoire de la haie, "
        "la cohérence entre le dossier et le document de décision doit être vérifiée.",
    ),
    "prefectural_order": (
        "missing_prefectural_order",
        "Pour clore le dossier avec cette décision, un document de décision "
        "doit être joint au dossier.",
    ),
    "applicant_message": (
        "missing_applicant_message",
        "Pour clore le dossier, un message doit être envoyé au demandeur.",
    ),
}


class SimulationCheckWidget(forms.CheckboxInput):
    """Checkbox rendered inside a richer "verify the simulation" block."""

    field_template_name = "haie/petitions/forms/fields/simulation_check.html"


class StateChangeForm(forms.ModelForm):
    """Form for updating petition project's stage.

    When the dossier is being closed (stage = "closed"), three additional
    fields become relevant, depending on the decision:
    - simulation_check: mandatory except for "dropped" (not persisted, it is
      only a procedural confirmation by the instructor);
    - prefectural_order: mandatory for "express_agreement" and "opposition";
    - applicant_message: mandatory for every decision, sent to the applicant
      through the Démarches Simplifiées messagerie.
    """

    simulation_check = forms.BooleanField(
        label="J'ai vérifié que la simulation active correspond bien "
        "à la version définitive.",
        required=False,
        widget=SimulationCheckWidget(),
    )
    prefectural_order = forms.FileField(
        label="Document de décision",
        required=False,
        help_text="""Exemple : arrêté préfectoral, courrier, etc.<br />
            Pour consigner plusieurs documents, utiliser une archive au format zip.<br />
            Formats autorisés : images (png, jpg), pdf, zip.<br>
            Taille maximale autorisée : 20 Mo.
        """,
        validators=[validate_file_size, validate_extension, validate_mime_type],
    )
    applicant_message = forms.CharField(
        label="Message au demandeur",
        required=False,
        help_text="""
        Précisez les motifs de la décision et les éléments du dossier sur lesquels elle s'appuie.<br />
        Ce message sera transmis au demandeur avec le document de décision en pièce jointe.
        """,
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    field_order = [
        "stage",
        "due_date",
        "decision",
        "status_date",
        "update_comment",
        "simulation_check",
        "prefectural_order",
        "applicant_message",
    ]

    class Meta:
        model = StatusLog
        fields = [
            "stage",
            "due_date",
            "decision",
            "status_date",
            "update_comment",
            "prefectural_order",
            "applicant_message",
        ]
        help_texts = {
            "update_comment": "Ce commentaire ne sera visible que par les services instructeurs dans l'historique du dossier.",  # noqa: E501
        }
        labels = {
            "due_date": "Échéance de l'étape",
        }
        widgets = {
            "stage": ProjectStageField(),
            "update_comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, is_paused=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_paused = is_paused
        self.fields["due_date"].widget.attrs["placeholder"] = "JJ/MM/AAAA"
        self.fields["status_date"].widget.attrs["placeholder"] = "JJ/MM/AAAA"
        # Pass field errors to the widget after validation
        for name, field in self.fields.items():
            bound_field = self[name]
            if bound_field.errors:
                field.widget.errors = bound_field.errors

    def clean(self):
        cleaned_data = super().clean()

        if self.is_paused:
            raise ValidationError(
                "Impossible de modifier l'état du dossier tant qu'il est "
                "en attente de compléments.",
                code="modification_while_paused",
            )
        stage = cleaned_data.get("stage")
        decision = cleaned_data.get("decision")

        if stage == "closed" and decision == "unset":
            self.add_error(
                "decision",
                ValidationError(
                    "Pour clore le dossier, le champ « Décision » doit être renseigné avec une valeur "
                    "définitive (autre que « À déterminer »).",
                    code="closed_without_decision",
                ),
            )

        previous_stage = self.initial["stage"]
        transition = (previous_stage, stage)
        if transition in FORBIDDEN_STAGE_TRANSITIONS:
            self.add_error(
                "stage",
                ValidationError(
                    FORBIDDEN_STAGE_TRANSITIONS[transition],
                    code="forbidden_transition",
                ),
            )

        if stage == "closed":
            self.clean_closing_fields(cleaned_data)
        else:
            # The closing fields are not displayed for other stages, ignore
            # any stray submitted value.
            cleaned_data["simulation_check"] = False
            cleaned_data["prefectural_order"] = None
            cleaned_data["applicant_message"] = ""

        return cleaned_data

    def reset_hidden_closing_fields(self, cleaned_data):
        """Force the fields hidden by the closing UI to their closing value.

        Closing is always effective immediately, without internal comment nor
        next due date. Errors on those fields are popped from `self._errors`
        directly, as the Form API offers no way to clear a single field error
        once its value is overridden server-side.
        """
        for field in ("update_comment", "due_date", "status_date"):
            self._errors.pop(field, None)
        cleaned_data["update_comment"] = ""
        cleaned_data["due_date"] = None
        cleaned_data["status_date"] = timezone.localdate()

    def clean_closing_fields(self, cleaned_data):
        """Enforce the closing requirements, depending on the decision.

        See the class docstring and CLOSING_FIELD_REQUIREMENTS for the
        requirements matrix.
        """
        self.reset_hidden_closing_fields(cleaned_data)

        decision = cleaned_data.get("decision")
        required_fields = CLOSING_FIELD_REQUIREMENTS.get(decision)
        if required_fields is None:
            # Closing without a final decision: the parent clean() already
            # reports the error, the closing fields are not enforced.
            return

        for field, (code, message) in CLOSING_FIELD_ERRORS.items():
            if field in required_fields and not cleaned_data.get(field):
                self.add_error(field, ValidationError(message, code=code))

        if "prefectural_order" not in required_fields:
            cleaned_data["prefectural_order"] = None


def three_months_from_now():
    now = timezone.now()

    # Very naive strategy for "three months from now", but it is just for the
    # default field value, so there is no need to be super clever here.
    delta = timedelta(days=3 * 30 + 1)
    res = now + delta
    return res


def request_for_info_message():
    """Format the default text for request for information message."""
    date = three_months_from_now()
    date_fmt = date_format(date, "d F Y")
    message = dedent(
        f"""
        Bonjour,

        Il apparaît que des informations sont manquantes pour instruire votre demande.

        Vous avez jusqu'au {date_fmt} pour les fournir.

        ***Liste des compléments à fournir***


        Cordialement,
        L'instructeur / le service instructeur.
    """
    )
    return message.strip()


class RequestAdditionalInfoForm(forms.Form):
    """Let an instructor pause the instruction and request for more information."""

    info_due_date = forms.DateField(
        label="Date limite de réponse du demandeur",
        required=True,
        initial=three_months_from_now,
    )
    request_message = forms.CharField(
        label="Message au demandeur",
        required=True,
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="""
        Ce message, à compléter par vos soins, sera envoyé au demandeur pour solliciter
        les compléments et l'informer de la suspension du délai en attendant sa réponse.
        Une fois envoyé, vous pourrez le retrouver dans la messagerie.
        """,
        initial=request_for_info_message,
    )

    def clean_info_due_date(self):
        info_due_date = self.cleaned_data["info_due_date"]
        today = timezone.now().date()

        if info_due_date < today:
            raise ValidationError(
                "La date limite ne peut pas être dans le passé.",
                code="date_in_past",
            )

        max_date = three_months_from_now().date()
        if info_due_date > max_date:
            raise ValidationError(
                "La date limite ne peut pas dépasser 3 mois à compter d'aujourd'hui.",
                code="date_exceeds_three_months",
            )

        return info_due_date


def today_formatted():
    """[type=date] input require values formatted in iso 8601."""

    return timezone.now().date().isoformat()


class ResumeProcessingForm(forms.Form):
    """Resume instruction processing."""

    info_receipt_date = forms.DateField(
        label="Date de réception des pièces",
        required=True,
        initial=today_formatted,
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "off"}),
    )


USER_TYPE = (
    ("petitioner", "Demandeur"),
    ("instructor", "Instructeur"),
)


def list_moulinette_errors(moulinette):
    """Returns an invalid moulinette's errors as field-prefixed messages."""
    fields = moulinette.get_prefixed_fields()
    messages = []
    for field_name, field_errors in moulinette.form_errors.items():
        field = fields.get(field_name)
        for message in field_errors:
            if field:
                message = f"{field.label} : {message}"
            messages.append(message)

    return messages


def validate_simulation_url(url):
    """Tells whether an url is a valid simulation, and details why if it is not.

    Returns ``(is_valid, errors)`` where ``errors`` is the field-prefixed list
    from the moulinette (empty when the url builds no moulinette at all). Shared
    by the creation form and the activation view so both apply the same rule.
    """
    is_valid, errors = True, []

    moulinette = MoulinetteUrl(url).get_moulinette()
    if moulinette is None:
        is_valid, errors = False, []
    elif not moulinette.is_valid():
        is_valid, errors = False, list_moulinette_errors(moulinette)

    return is_valid, errors


class SimulationForm(forms.ModelForm):
    moulinette_url = forms.URLField(
        label="Lien vers la simulation",
        help_text="Collez ici le lien de la page de simulation alternative",
        required=True,
    )
    source = forms.ChoiceField(
        label="Auteur",
        choices=USER_TYPE,
        widget=forms.RadioSelect,
        help_text="Qui est à l'origine de la simulation alternative ?",
    )
    comment = forms.CharField(
        label="Commentaire",
        widget=forms.Textarea(attrs={"rows": "3"}),
        max_length=2048,
    )

    class Meta:
        model = Simulation
        fields = ["moulinette_url", "source", "comment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store the underlying moulinette form errors
        self.moulinette_errors = []

    def clean_moulinette_url(self):
        url = self.cleaned_data["moulinette_url"]

        # Reject a url that is not a valid simulation. The underlying errors are
        # exposed so the template can list them below the field.
        is_valid, errors = validate_simulation_url(url)
        if not is_valid:
            self.moulinette_errors = errors
            raise ValidationError(
                "Il semble que l'url ne corresponde pas à une page de simulation valide.",
                code="invalid_moulinette",
            )

        return MoulinetteUrl(url).url
