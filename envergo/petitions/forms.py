from django import forms

from envergo.petitions.models import PetitionProject


class PetitionProjectForm(forms.ModelForm):
    """Form for creating a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "moulinette_url",
        ]
