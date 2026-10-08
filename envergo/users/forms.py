import logging
import time

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from envergo.users.models import User
from envergo.utils.fields import AllowDisabledSelect, HoneypotInput, NoIdnEmailField

logger = logging.getLogger(__name__)

# Seconds. Below the fastest human signup observed in production logs (6.5 s).
MIN_FILL_DURATION = 5


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
    website = forms.CharField(label="Site web", required=False, widget=HoneypotInput)
    displayed_at = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["email", "name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["placeholder"] = "Prénom Nom"
        # Signed so the client cannot fake an older display time.
        self.fields["displayed_at"].initial = signing.dumps(time.time())

    def is_bot_submission(self):
        """Tell whether the submission comes from a spam bot. Safe to call before validation."""
        honeypot_filled = bool(self["website"].data)
        submitted_too_fast = self.seconds_since_display() < MIN_FILL_DURATION
        is_bot = honeypot_filled or submitted_too_fast

        if is_bot:
            logger.warning(
                "Bot signup rejected (honeypot filled: %s, submitted too fast: %s)",
                honeypot_filled,
                submitted_too_fast,
            )
        return is_bot

    def seconds_since_display(self):
        """Seconds spent on the form. Zero when the display time is missing or forged."""
        seconds = 0
        signed_display_time = self["displayed_at"].data or ""
        try:
            displayed_at = signing.loads(signed_display_time)
            seconds = time.time() - displayed_at
        except signing.BadSignature:
            pass
        return seconds

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
