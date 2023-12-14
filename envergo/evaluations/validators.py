import re

from django.core.validators import RegexValidator

# fmt: off
PERMIT_NUMBER_RE = (
    r"^"
    r"(PC|PA|DP|CU)"
    r"(?P<department>\d{3})"
    r"(?P<commune>\d{3})"
    r"(?P<year>\d{2})"
    r"(?P<file>[\w\d]{5})"
    r"$"
)


application_number_validator = RegexValidator(
    regex=PERMIT_NUMBER_RE,
    flags=re.I,
    message="""Le numéro de dossier doit être constitué de quinze
    caractères et commencer par « PA », « PC », « DP » ou « CU »""",
)
