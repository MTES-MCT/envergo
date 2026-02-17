import io
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from envergo.utils.validators import validate_mime


class DummyFile(io.BytesIO):
    def __init__(self, content=b"dummy", content_type="application/octet-stream"):
        super().__init__(content)
        self.content_type = content_type


@pytest.mark.parametrize(
    "detected,allowed,should_raise",
    [
        ("image/png", {"image/png"}, False),
        ("image/jpeg", {"image/png"}, True),
    ],
)
@patch("envergo.utils.validators.magic.from_buffer")
def test_validate_mime(mock_magic, detected, allowed, should_raise):
    mock_magic.return_value = detected
    file = DummyFile()

    if should_raise:
        with pytest.raises(ValidationError):
            validate_mime(file, allowed)
    else:
        validate_mime(file, allowed)
