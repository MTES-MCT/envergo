import pytest
from django.core.exceptions import ValidationError

from envergo.evaluations.validators import application_number_validator


def test_application_number_validator():
    valid_numbers = [
        "PC05412621D1029",
        "PA05412621D1029",
        "PA05412621A1029",
        "pc05412621d1029",
    ]

    # Test will succeed if no exceptions are raised
    for number in valid_numbers:
        application_number_validator(number)

    invalid_numbers = [
        "test",
        "toto",
        "gloubiboulga",
        "AA04412621D1029",
        "AAAAAAAAAAAAAAA",
    ]

    for number in invalid_numbers:
        with pytest.raises(ValidationError):
            application_number_validator(number)
