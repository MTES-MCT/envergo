from datetime import date, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateRange

from envergo.geodata.tests.factories import DepartmentFactory
from envergo.moulinette.tests.factories import ConfigAmenagementFactory

pytestmark = pytest.mark.django_db


def test_is_amenagement_activated_ignores_expired_config():
    """is_amenagement_activated returns False when only expired configs exist."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    dept = DepartmentFactory()

    ConfigAmenagementFactory(
        department=dept,
        is_activated=True,
        validity_range=DateRange(one_year_ago, today, "[)"),
    )

    assert not dept.is_amenagement_activated()


def test_is_amenagement_activated_with_current_config():
    """is_amenagement_activated returns True when a currently valid config exists."""
    today = date.today()
    one_year_later = today + timedelta(days=365)
    dept = DepartmentFactory()

    ConfigAmenagementFactory(
        department=dept,
        is_activated=True,
        validity_range=DateRange(today, one_year_later, "[)"),
    )

    assert dept.is_amenagement_activated()
