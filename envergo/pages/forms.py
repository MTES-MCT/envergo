from django import forms


class DemarcheSimplifieeForm(forms.Form):
    moulinette_url = forms.URLField(required=True, label="Moulinette URL")
