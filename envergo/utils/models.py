from django.db import models
from django.utils.translation import gettext_lazy as _


def generate_reference():
    pass


class ReferencField(models.CharField):
    default_error_messages = {
        "invalid": _("“%(value)s” is not a valid EnvErgo reference."),
    }
    description = _("Unique and memorable (sortof) identifier")
    empty_strings_allowed = False

    def __init__(self, verbose_name=None, **kwargs):
        kwargs["max_length"] = 32
        kwargs["default"] = generate_reference
        super().__init__(verbose_name, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_length"]
        del kwargs["default"]
        return name, path, args, kwargs
