import logging
import re

from django import forms

logger = logging.getLogger(__name__)


def classpath(klass):
    return "{}.{}".format(klass.__module__, klass.__name__)


class StripWhitespaceMixin:
    """IntegerField that strips whitespace from input.

    Users often enter numbers with spaces as thousand separators (e.g., "8 000").
    This field removes all whitespace before validation.
    """

    def to_python(self, value):
        if isinstance(value, str):
            # The \s class matches all whitespaces (spaces, nbsp, tabs…)
            value = re.sub(r"\s", "", value)
        return super().to_python(value)


class NoInstanciateChoiceField(forms.TypedChoiceField):
    def prepare_value(self, value):
        """Fix prepared value.

        The `BoundField` class automatically instanciates values when they
        are callable, which we don't want, so we have to reverse this
        action here.

        See `django.forms.forms.BoundField.value`

        """
        if isinstance(value, type):
            prepared_val = classpath(value)
        else:
            prepared_val = value
        return prepared_val


class DisplayFieldMixin:
    """Mixin for display fields.

    Used to get specific fields label and help texte displayed in results"""

    def __init__(self, *args, **kwargs):
        display_label = kwargs.pop("display_label", None)
        display_unit = kwargs.pop("display_unit", None)
        display_help_text = kwargs.pop("display_help_text", None)
        get_display_value = kwargs.pop("get_display_value", None)
        if display_label is not None:
            self.display_label = display_label
        if display_unit is not None:
            self.display_unit = display_unit
        if display_help_text is not None:
            self.display_help_text = display_help_text
        if get_display_value is not None:
            self.get_display_value = get_display_value
        super().__init__(*args, **kwargs)


class DisplayChoiceField(DisplayFieldMixin, forms.ChoiceField):
    pass


class DisplayIntegerField(DisplayFieldMixin, StripWhitespaceMixin, forms.IntegerField):
    pass


class DisplayCharField(DisplayFieldMixin, forms.CharField):
    pass


class DisplayBooleanField(DisplayFieldMixin, forms.BooleanField):
    pass


def extract_choices(choices):
    """Extract form choices from a list of 3 items tuples : code, form label, display label."""
    return [(code, form_label) for code, form_label, _ in choices]


def extract_display_function(choices):
    """Extract a lambda method to display the label based on code
    from a list of 3 items tuples : code, form label, display label."""
    return lambda value: next(
        (choice[2] for choice in choices if choice[0] == value), None
    )


class UnitInput(forms.TextInput):
    """Render a text input with a custom prefix placeholder.

    This renders an input with a unit right next to it.
    """

    input_type = "text"
    template_name = "forms/widgets/text_unit.html"

    def __init__(self, unit, attrs=None):
        self.unit = unit
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["unit"] = self.unit
        return context
