import pytest
from django.core.exceptions import ValidationError

from envergo.evaluations.validators import application_number_validator


def test_application_number_validator():
    valid_numbers = [
        "PC04412621D1029",
        "PA04412621D1029",
        "PA04412621A1029",
        "PC 044 126 21 A1029",
        "pc 044 126 21 d1029",
        "pc   044     126 21            d1029",
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
