from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms.fields import FileField

from envergo.petitions.models import PetitionProject, StatusLog


class PetitionProjectForm(forms.ModelForm):
    """Form for creating a petition project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moulinette_url"].required = True

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
    allowed_extensions=["png", "jpg", "tiff", "jpeg", "pdf", "zip"],
)


class PetitionProjectInstructorMessageForm(forms.Form):
    """Form to send a message through demarches simplifiées API."""

    message_body = forms.CharField(
        label="Votre message",
        widget=forms.Textarea(
            attrs={"rows": 8, "placeholder": "Écrivez votre message ici…"}
        ),
    )

    additional_file = FileField(
        label="Fichier joint",
        required=False,
        help_text="""
            Formats autorisés : images (png, jpg), pdf, zip. <br>
            Maximum 20 Mo.
        """,
        validators=[validate_file_size, validate_extension],
    )

    class Meta:
        fields = ["message_body", "additional_file"]


class ProcedureForm(forms.ModelForm):
    """Form for updating petition project's stage."""

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

    class Meta:
        model = StatusLog
        fields = [
            "stage",
            "decision",
            "status_date",
            "update_comment",
        ]
        help_texts = {
            "stage": "Un dossier dans l'étape « à instruire » est encore modifiable par le pétitionnaire.",
        }
