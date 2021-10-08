from django import forms
from django.contrib.auth.forms import UserCreationForm

from envergo.users.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label="Votre adresse e-mail",
        required=True,
        help_text="Nous enverrons un e-mail de confirmation à cette adresse avant de valider le compte.",
    )
    name = forms.CharField(
        label="Votre nom complet",
        required=True,
        help_text="C'est ainsi que nous nous adresserons à vous dans nos communications.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["email", "name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["placeholder"] = "Prénom Nom"

    def clean_email(self):
        email = self.cleaned_data["email"]
        return email.lower()
