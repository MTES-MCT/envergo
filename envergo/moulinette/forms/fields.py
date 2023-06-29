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
