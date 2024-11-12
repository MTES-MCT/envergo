from django import forms

from envergo.moulinette.forms import MoulinetteFormHaie
from envergo.petitions.models import PetitionProject


class PetitionProjectForm(forms.ModelForm):
    """Form for creating a petition project.

    Some fields are inherited from the main moulinette form as it should be the source of this form.
    Some of these fields are not needed for the petition project creation but for pre-filling the
    dossier on demarches-simplifiees.fr.
    """

    profil = MoulinetteFormHaie.base_fields["profil"]
    haies = MoulinetteFormHaie.base_fields["haies"]

    class Meta:
        model = PetitionProject
        fields = [
            "moulinette_url",
        ]