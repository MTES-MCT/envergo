from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms.widgets import Select
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
        """Prevent case related issues."""
        email = self.cleaned_data.get("email")
        return email.lower()

    def clean(self):
        # Disable unique validation. We will do it manually
        self._validate_unique = False
        return self.cleaned_data

    def full_clean(self):
        """Check that the email is unique.

        We NEVER want to display the "A user with that email already exists" message.
        So in the view, there is a custom check. If the "unique" error is the ONLY form
        error, we don't display the error and send an activation email instead.

        Thus, we want to check for email unicity IF AND ONLY IF there are no other
        errors in the form.

        We have to do this check in the `post_clean` method because the password
        validation happens in the `_post_clean` method in the parent form.
        """
        super().full_clean()

        if not self.errors:
            # Prevent registrations with existing email addresses
            email = self.cleaned_data.get("email")
            if email and self._meta.model.objects.filter(email__iexact=email).exists():
                error = ValidationError(
                    "Un utilisateur avec cette adresse e-mail existe déjà.",
                    code="unique",
                )
                self.add_error("email", error)


class AllowDisabledSelect(Select):
    """A select widget (drop down list) that will disable options where the value is set to an empty string"""

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option_dict = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if not value:
            option_dict["attrs"]["disabled"] = "disabled"
        return option_dict


class NewsletterOptInForm(forms.Form):
    type = forms.ChoiceField(
        required=True,
        label="Vous êtes",
        choices=(
            ("", "Sélectionner une option"),
            ("instructeur", "Service instructeur urbanisme"),
            ("amenageur", "Aménageur"),
            ("geometre", "Géomètre"),
            ("bureau", "Bureau d'études"),
            ("architecte", "Architecte"),
            ("particulier", "Particulier"),
            ("autre", "Autre"),
        ),
        widget=AllowDisabledSelect(attrs={"placeholder": "Sélectionnez votre type"}),
    )
    email = NoIdnEmailField(
        required=True,
        label="Votre adresse email",
        widget=forms.EmailInput(attrs={"placeholder": "ex. : nom@domaine.fr"}),
    )
