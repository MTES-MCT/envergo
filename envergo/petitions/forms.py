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


class OnagreForm(forms.ModelForm):
    """Form for adding an ONAGRE number to a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "onagre_number",
        ]


class InstructorFreeMentionForm(forms.ModelForm):
    """Form for adding an instructor_free_mention to a petition project."""

    class Meta:
        model = PetitionProject
        fields = [
            "instructor_free_mention",
        ]
        widgets = {
            "instructor_free_mention": forms.Textarea(attrs={"rows": 3}),
        }
