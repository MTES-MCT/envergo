from django import forms
from django.core.exceptions import ValidationError

from envergo.petitions.models import PetitionProject, StatusLog
from envergo.utils.fields import ProjectStageField


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


class PetitionProjectInstructorMessageForm(forms.Form):
    """Form to send a message through demarches simplifiées API."""

    message_body = forms.CharField(
        label="Votre message",
        widget=forms.Textarea(
            attrs={"rows": 8, "placeholder": "Écrivez votre message ici…"}
        ),
    )

    class Meta:
        fields = [
            "message_body",
        ]


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
            "update_comment": "Commentaire interne expliquant le contexte et les raisons du changement.",
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
