import logging

from django import forms

logger = logging.getLogger(__name__)


def classpath(klass):
    return "{}.{}".format(klass.__module__, klass.__name__)


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
    def __init__(self, *args, **kwargs):
        self._display_label = kwargs.pop("display_label", kwargs.get("label", None))
        self.display_unit = kwargs.pop("display_unit", None)
        get_display_value = kwargs.pop("get_display_value", None)
        if get_display_value:
            self.get_display_value = get_display_value
        super().__init__(*args, **kwargs)

    @property
    def display_label(self):
        return self._display_label


class DisplayChoiceField(DisplayFieldMixin, forms.ChoiceField):
    pass


class DisplayIntegerField(DisplayFieldMixin, forms.IntegerField):
    pass
