from django import forms

from envergo.moulinette.forms import MoulinetteFormHaie


class DemarcheSimplifieeForm(forms.Form):
    moulinette_url = forms.URLField(required=True, label="Moulinette URL")
    profil = MoulinetteFormHaie.base_fields["profil"]
