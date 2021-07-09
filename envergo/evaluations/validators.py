import re

from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

# fmt: off
PERMIT_NUMBER_RE = (
    r"^"
    r"(PC|PA)"
    r"(?P<department>\d{3})"
    r"(?P<commune>\d{3})"
    r"(?P<year>\d{2})"
    r"(?P<file>[\w\d]{5})"
    r"$"
)


class IgnoreWhitespacesRegexValidator(RegexValidator):
    def __call__(self, value):
        return super().__call__(value.strip().replace(' ', ''))


application_number_validator = IgnoreWhitespacesRegexValidator(
    regex=PERMIT_NUMBER_RE,
    message=_('The application number format is invalid.'),
    flags=re.I
)
