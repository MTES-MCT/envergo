from django.core.exceptions import ValidationError
from django.db import models
from django.utils.module_loading import import_string

from envergo.moulinette.forms.fields import MoulinetteCriterionChoiceField
from envergo.moulinette.regulations import MoulinetteCriterion


def classpath(klass):
    return "{}.{}".format(klass.__module__, klass.__name__)


# Shamelessly stolen from StackOverflow
# https://stackoverflow.com/a/3862310/1062495
def get_subclasses(cls):
    """Recursively get all subclasses and sub-subclasses of a class."""
    for subclass in cls.__subclasses__():
        yield from get_subclasses(subclass)
        yield subclass


class CriterionChoiceField(models.Field):
    """Custom model field to select a `MoulinetteCriterion` subclass.

    At the database level, we store the full classpath.
    """

    description = "Field to select a MoulinetteCriterion subclass."

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 256
        super().__init__(*args, **kwargs)
        self.choices = self._get_all_criteria()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_length"]
        return name, path, args, kwargs

    def _get_all_criteria(self):
        """Return the list of all available criteria."""

        criteria = [
            (classpath(s), f"{s.choice_label}")
            for s in get_subclasses(MoulinetteCriterion)
        ]
        return criteria

    def from_db_value(self, value, expression, connection):
        try:
            val = self.to_python(value)
        except ValidationError:
            val = None
        return val

    def to_python(self, value):
        """Converts the stored string to a python type."""

        if value == "" or value is None:
            return None

        if isinstance(value, str):
            try:
                value = import_string(value)
            except:  # noqa
                raise ValidationError("The class {} does not exist".format(value))

        if not isinstance(value, type):
            raise ValidationError("This should be a python class.")

        return value

    def validate(self, value, model_instance):
        if not issubclass(value, MoulinetteCriterion):
            raise ValidationError("This is not a valid Criterion class")

    def get_prep_value(self, value):
        """Converts type to string."""

        if isinstance(value, type):
            value = classpath(value)

        return value

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)

    def formfield(self, **kwargs):
        defaults = {"choices_form_class": MoulinetteCriterionChoiceField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
