import logging

from django import forms

logger = logging.getLogger(__name__)


def classpath(klass):
    return "{}.{}".format(klass.__module__, klass.__name__)


class CriterionSelect(forms.Select):
    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label) in enumerate(self.choices):
            if option_value is None:
                option_value = ""

            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = option_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(option_value, option_label)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel in choices:
                logger.info(str(subvalue))
                logger.info(value)
                selected = str(subvalue) in value and (
                    not has_selected or self.allow_multiple_selected
                )
                has_selected |= selected
                subgroup.append(
                    self.create_option(
                        name,
                        subvalue,
                        sublabel,
                        selected,
                        index,
                        subindex=subindex,
                        attrs=attrs,
                    )
                )
                if subindex is not None:
                    subindex += 1
        return groups

    def create_option(self, *args, **kwargs):
        res = super().create_option(*args, **kwargs)
        return res


class MoulinetteCriterionChoiceField(forms.TypedChoiceField):
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
