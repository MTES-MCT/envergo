from django.forms import EmailField

from envergo.utils.validators import NoIdnEmailValidator


class NoIdnEmailField(EmailField):
    """
    Our email sending tool Brevo do not support Internationalized Domain Names (IDN).
    This Field is a subclass of Django's EmailField that raises a validation error if there is diacritics,
    ligatures or non-Latin character in the domain name.
    """

    default_validators = [NoIdnEmailValidator()]
