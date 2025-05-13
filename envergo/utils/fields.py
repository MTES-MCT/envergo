from django.forms import EmailField
from django.forms.widgets import Select

from envergo.utils.validators import NoIdnEmailValidator


class NoIdnEmailField(EmailField):
    """
    Our email sending tool Brevo do not support Internationalized Domain Names (IDN).
    This Field is a subclass of Django's EmailField that raises a validation error if there is diacritics,
    ligatures or non-Latin character in the domain name.
    """

    default_validators = [NoIdnEmailValidator()]


class AllowDisabledSelect(Select):
    """A select widget (drop down list) that is disabling options where the value is set to an empty string"""

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option_dict = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if not value:
            option_dict["attrs"]["disabled"] = "disabled"
        return option_dict


def get_human_readable_value(choices, key):
    """Get the human-readable value of a choice field."""
    for choice_key, human_readable in choices:
        if choice_key == key:
            return human_readable
    return None
