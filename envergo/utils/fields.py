from django.forms import ClearableFileInput, EmailField, FileField
from django.forms.widgets import RadioSelect, Select

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


class HedgeChoiceField(RadioSelect):
    template_name = "haie/forms/widgets/hedge_radio.html"
    option_template_name = "haie/forms/widgets/hedge_radio_option.html"


# See https://docs.djangoproject.com/en/4.2/topics/http/file-uploads/#uploading-multiple-files
class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ProjectStageField(Select):
    template_name = "haie/forms/widgets/project_stage.html"
    option_template_name = "django/forms/widgets/select_option.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        from envergo.petitions.models import STAGES

        context["STAGES"] = STAGES
        context["widget"]["errors"] = getattr(self, "errors", [])
        return context
