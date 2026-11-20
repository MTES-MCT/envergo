from datetime import timedelta

import pytest
from django.utils import timezone

from envergo.security.models import Vulnerability


@pytest.mark.parametrize(
    "days_open, expected_age",
    [(2, "recent"), (3, "aging"), (7, "aging"), (8, "overdue")],
)
def test_open_age_escalates_with_time(days_open, expected_age):
    """The age tag turns overdue only past seven full days."""
    detected_at = timezone.now() - timedelta(days=days_open)
    vulnerability = Vulnerability(detected_at=detected_at)

    assert vulnerability.open_age == expected_age
