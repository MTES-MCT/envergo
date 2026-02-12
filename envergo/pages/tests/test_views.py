from datetime import date, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateRange
from django.test import override_settings
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import DepartmentFactory
from envergo.moulinette.tests.factories import ConfigAmenagementFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site():
    return SiteFactory()


@pytest.mark.urls("config.urls_amenagement")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="testserver")
def test_availability_info_excludes_expired_active_configs(client):
    """configs_available only lists active configs valid at today's date."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    one_year_later = today + timedelta(days=365)
    dept = DepartmentFactory()

    # Expired active config — should NOT appear in configs_available
    ConfigAmenagementFactory(
        department=dept,
        is_activated=True,
        validity_range=DateRange(one_year_ago, today, "[)"),
    )
    # Current active config — should appear in configs_available
    current_config = ConfigAmenagementFactory(
        department=dept,
        is_activated=True,
        validity_range=DateRange(today, one_year_later, "[)"),
    )

    url = reverse("faq_availability_info")
    response = client.get(url)

    assert response.status_code == 200
    configs_available = list(response.context["configs_available"])
    assert configs_available == [current_config]


@pytest.mark.urls("config.urls_amenagement")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="testserver")
def test_availability_info_shows_upcoming_departments_without_duplicates(client):
    """configs_soon lists departments with inactive configs, without duplicates."""
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    one_year_later = today + timedelta(days=365)
    two_years_later = today + timedelta(days=730)
    dept = DepartmentFactory()

    # Two inactive configs for the same department (e.g. past and future periods)
    # — the department should appear only once in configs_soon
    ConfigAmenagementFactory(
        department=dept,
        is_activated=False,
        validity_range=DateRange(one_year_ago, today, "[)"),
    )
    ConfigAmenagementFactory(
        department=dept,
        is_activated=False,
        validity_range=DateRange(one_year_later, two_years_later, "[)"),
    )

    url = reverse("faq_availability_info")
    response = client.get(url)

    assert response.status_code == 200
    configs_soon = list(response.context["configs_soon"])
    assert configs_soon == [dept]


@pytest.mark.urls("config.urls_amenagement")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="testserver")
def test_availability_info_excludes_already_active_departments_from_soon(client):
    """A department with an active config now and an inactive future config
    should appear in configs_available but NOT in configs_soon."""
    today = date.today()
    one_year_later = today + timedelta(days=365)
    two_years_later = today + timedelta(days=730)
    dept = DepartmentFactory()

    # Currently active config
    current_config = ConfigAmenagementFactory(
        department=dept,
        is_activated=True,
        validity_range=DateRange(today, one_year_later, "[)"),
    )
    # Future inactive config (being prepared)
    ConfigAmenagementFactory(
        department=dept,
        is_activated=False,
        validity_range=DateRange(one_year_later, two_years_later, "[)"),
    )

    url = reverse("faq_availability_info")
    response = client.get(url)

    assert response.status_code == 200
    configs_available = list(response.context["configs_available"])
    assert configs_available == [current_config]
    configs_soon = list(response.context["configs_soon"])
    assert configs_soon == []
