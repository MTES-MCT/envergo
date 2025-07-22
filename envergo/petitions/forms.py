from django import forms
from django.utils import timezone

from envergo.petitions.models import PetitionProject


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


class ProcedureForm(forms.ModelForm):
    """Form for updating petition project's stage."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # force initial value (overrides instance)
        self.initial["stage_date"] = timezone.now()
        self.initial["stage_update_comment"] = ""

        self.fields["stage_date"].required = True
        self.fields["stage_update_comment"].required = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.stage_updated_at = timezone.now()
        if commit:
            instance.save()
        return instance

    class Meta:
        model = PetitionProject
        fields = [
            "stage",
            "decision",
            "stage_date",
            "stage_update_comment",
        ]
        labels = {
            "stage_date": "Date effective du changement",
            "stage_update_comment": "Commentaire",
        }
        help_texts = {
            "stage_date": "Vous pouvez choisir une date rétroactive si nécessaire.",
            "stage_update_comment": "Ajouter un commentaire expliquant le contexte du changement.",
        }


class PetitionProjectInstructorMessageForm(forms.Form):
    """Form to send a message through demarche simplifie API."""

    message_body = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))

    def send_message(self):
        # send message using the self.cleaned_data dictionary
        pass
