from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from envergo.users.models import User
from envergo.utils.fields import NoIdnEmailField

# This string is used in django's original AuthenticationForm
# There is a typo in the string translation, so we add this variable here
# so it is caught by `makemessages` and we can override it in our own
# locale file.
_INVALID_LOGIN_ERROR_MSG = (
    _(
        "Please enter a correct %(username)s and password. Note that both "
        "fields may be case-sensitive."
    ),
)


class RegisterForm(UserCreationForm):
    email = NoIdnEmailField(
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
