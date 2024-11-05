from django import forms

from envergo.moulinette.forms import MoulinetteFormHaie
from envergo.petitions.models import PetitionProject


class PetitionProjectForm(forms.ModelForm):
    profil = MoulinetteFormHaie.base_fields["profil"]
    haies = MoulinetteFormHaie.base_fields["haies"]

    class Meta:
        model = PetitionProject
        fields = [
            "moulinette_url",
        ]
