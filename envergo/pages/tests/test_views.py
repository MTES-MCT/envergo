from datetime import date, timedelta

import pytest
from django.db.backends.postgresql.psycopg_any import DateRange
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import DepartmentFactory
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    DCConfigHaieFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site():
    return SiteFactory()


@pytest.mark.urls("config.urls_amenagement")
class TestAvailabilityInfo:

    @pytest.fixture(autouse=True)
    def _settings(self, settings):
        settings.ENVERGO_AMENAGEMENT_DOMAIN = "testserver"

    def test_excludes_expired_active_configs(self, client):
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

    def test_shows_upcoming_departments_without_duplicates(self, client):
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

    def test_excludes_already_active_departments_from_soon(self, client):
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


@pytest.mark.haie
class TestHomeHaie:
    """Test the active departments display on home page."""

    def test_only_activated_and_valid_configs_shown(self, client):
        """The button list should only include activated configs valid today."""
        today = date.today()
        one_year_ago = today - timedelta(days=365)
        one_year_later = today + timedelta(days=365)
        dept = DepartmentFactory()

        # Expired activated config — should NOT appear
        DCConfigHaieFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(one_year_ago, today, "[)"),
        )
        # Current activated config — should appear
        current = DCConfigHaieFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(today, one_year_later, "[)"),
        )

        response = client.get(reverse("home"))

        assert response.status_code == 200
        configs = list(response.context["activated_configs"])
        assert configs == [current]

    def test_inactive_configs_not_shown(self, client):
        """Inactive configs should not appear in the button list even if valid."""
        DCConfigHaieFactory(is_activated=False)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert list(response.context["activated_configs"]) == []

    def test_no_configs_renders_empty_button_list(self, client):
        """The page renders without error when no configs exist."""
        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert list(response.context["activated_configs"]) == []

    def test_activated_department_redirects_to_triage(self, client):
        """Selecting an activated department should redirect to the triage page."""
        config = DCConfigHaieFactory(is_activated=True)

        response = client.post(
            reverse("home"),
            {"department": config.department.id},
        )

        assert response.status_code == 302
        assert reverse("triage") in response.url
        assert f"department={config.department.department}" in response.url

    def test_inactive_department_does_not_redirect(self, client):
        """Selecting an inactive department should NOT redirect to triage."""
        config = DCConfigHaieFactory(is_activated=False)

        response = client.post(
            reverse("home"),
            {"department": config.department.id},
        )

        assert response.status_code == 200
        assert response.context["department"] == config.department

    def test_expired_config_does_not_redirect(self, client):
        """An expired config should not trigger a redirect, even if activated."""
        today = date.today()
        one_year_ago = today - timedelta(days=365)

        config = DCConfigHaieFactory(
            is_activated=True,
            validity_range=DateRange(one_year_ago, today, "[)"),
        )

        response = client.post(
            reverse("home"),
            {"department": config.department.id},
        )

        assert response.status_code == 200
        assert response.context["department"] == config.department

    def test_multiple_configs_uses_valid_one(self, client):
        """When a department has multiple configs, POST uses the currently valid one."""
        today = date.today()
        one_year_ago = today - timedelta(days=365)
        one_year_later = today + timedelta(days=365)
        dept = DepartmentFactory()

        # Expired config
        DCConfigHaieFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(one_year_ago, today, "[)"),
        )
        # Current config
        DCConfigHaieFactory(
            department=dept,
            is_activated=True,
            validity_range=DateRange(today, one_year_later, "[)"),
        )

        response = client.post(
            reverse("home"),
            {"department": dept.id},
        )

        assert response.status_code == 302
        assert reverse("triage") in response.url

    def test_department_with_no_config(self, client):
        """Selecting a department with no config should render the page (no redirect)."""
        dept = DepartmentFactory()

        response = client.post(
            reverse("home"),
            {"department": dept.id},
        )

        assert response.status_code == 200
        assert response.context["department"] == dept
        assert response.context["config"] is None

    def test_without_department(self, client):
        """POST without selecting a department should render the page."""
        response = client.post(reverse("home"), {})

        assert response.status_code == 200
