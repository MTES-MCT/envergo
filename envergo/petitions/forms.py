from django import forms

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


class PetitionProjectInstructorForm(forms.ModelForm):
    """Form for adding instructor fields to a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "onagre_number",
            "instructor_free_mention",
        ]
        widgets = {
            "onagre_number": forms.TextInput(
                attrs={"placeholder": "AAAA-MM-XXX-NNNNN"}
            ),
            "instructor_free_mention": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Ajoutez vos notes ici…"},
            ),
        }
        labels = {"instructor_free_mention": "Notes libres"}
