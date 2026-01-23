from datetime import timedelta
from textwrap import dedent

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms.fields import FileField
from django.utils import timezone
from django.utils.formats import date_format

from envergo.moulinette.utils import MoulinetteUrl
from envergo.petitions.models import PetitionProject, Simulation, StatusLog
from envergo.utils.fields import ProjectStageField
from envergo.utils.urls import remove_from_qs


class PetitionProjectForm(forms.ModelForm):
    """Form for creating a petition project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moulinette_url"].required = True

    def clean_moulinette_url(self):
        # remove the date parameter from the moulinette url if there is one
        moulinette_url = self.cleaned_data["moulinette_url"]
        cleaned_moulinette_url = remove_from_qs(moulinette_url, "date")
        return cleaned_moulinette_url

    class Meta:
        model = PetitionProject
        fields = [
            "moulinette_url",
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
        ]
        widgets = {
            "instructor_free_mention": forms.Textarea(
                attrs={
                    "rows": 10,
                    "placeholder": "Ajoutez vos notes ici…",
                },
            ),
        }
        labels = {"instructor_free_mention": ""}
        help_texts = {
            "instructor_free_mention": "Partagez ici tout ce qui est utile à votre suivi de la demande, "
            "ou à la collaboration entre services instructeurs. "
            "Cliquer sur « Enregistrer » pour sauvegarder."
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


class PetitionProjectInstructorMessageForm(forms.Form):
    """Form to send a message through demarches simplifiées API."""

    message_body = forms.CharField(
        label="Votre message",
        help_text="""Au format HTML ou texte simple.
            <br>À noter que les liens seront cliquables s'ils commencent par "https://" ou "www".
        """,
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
        validators=[validate_file_size, validate_extension],
    )

    class Meta:
        fields = ["message_body", "additional_file"]


class ProcedureForm(forms.ModelForm):
    """Form for updating petition project's stage."""

    class Meta:
        model = StatusLog
        fields = [
            "stage",
            "due_date",
            "decision",
            "status_date",
            "update_comment",
        ]
        help_texts = {
            "update_comment": "Commentaire interne. Aucun message ne sera envoyé au demandeur.",
        }
        labels = {
            "due_date": "Échéance de l'étape",
        }
        widgets = {
            "stage": ProjectStageField(),
            "update_comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_date"].widget.attrs["placeholder"] = "JJ/MM/AAAA"
        self.fields["status_date"].widget.attrs["placeholder"] = "JJ/MM/AAAA"
        # Pass field errors to the widget after validation
        for name, field in self.fields.items():
            bound_field = self[name]
            if bound_field.errors:
                field.widget.errors = bound_field.errors

    def clean(self):
        cleaned_data = super().clean()
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

        if stage == "closed" and previous_stage == "to_be_processed":
            self.add_error(
                "stage",
                ValidationError(
                    "Pour clore le dossier, il faut passer par une étape intermédiaire (autre que « À instruire »).",
                    code="to_be_processed_to_closed",
                ),
            )
        elif stage == "to_be_processed" and previous_stage == "closed":
            self.add_error(
                "stage",
                ValidationError(
                    "Pour repasser le dossier à l'étape « À instruire », il faut passer par une étape "
                    "intermédiaire (autre que « Dossier clos »).",
                    code="closed_to_to_be_processed",
                ),
            )
        elif stage == "closed" and previous_stage == "closed":
            self.add_error(
                "stage",
                ValidationError(
                    "Pour pouvoir changer la décision d'un dossier clos il faut d'abord le repasser à une "
                    "étape d'instruction.",
                    code="closed_to_closed",
                ),
            )

        return cleaned_data


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

    due_date = forms.DateField(
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

    def clean_moulinette_url(self):
        url = self.cleaned_data["moulinette_url"]
        moulinette_url = MoulinetteUrl(url)
        if not moulinette_url.is_valid():
            raise ValidationError(
                "Il semble que l'url ne corresponde pas à une page de simulation valide.",
                code="invalid_moulinette",
            )
        return moulinette_url.url
