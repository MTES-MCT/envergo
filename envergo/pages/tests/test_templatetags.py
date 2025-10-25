import factory
import pytest
from django.test import override_settings

from envergo.geodata.tests.factories import Department34Factory, DepartmentFactory
from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.users.models import User
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def inactive_haie_user_44() -> User:
    """Haie user with dept 44"""
    haie_user_44 = UserFactory(
        access_amenagement=False,
        access_haie=True,
        is_active=False,
    )
    department_44 = DepartmentFactory.create()
    haie_user_44.departments.add(department_44)
    return haie_user_44


@pytest.fixture
def instructor_haie_user_44() -> User:
    """Haie user with dept 44"""
    instructor_haie_user_44 = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
    )
    department_44 = DepartmentFactory.create()
    instructor_haie_user_44.departments.add(department_44)
    return instructor_haie_user_44


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_department_list(
    inactive_haie_user_44, instructor_haie_user_44, haie_user, admin_user, client, site
):

    ConfigHaieFactory()
    ConfigHaieFactory(department=factory.SubFactory(Department34Factory))

    # GIVEN an anonymous visitor

    # WHEN they visit homepage
    response = client.get("/")

    # THEN department menu is not diplayed
    content = response.content.decode()
    assert "Paramétrage" not in content

    # GIVEN an authenticated inactive user
    client.force_login(inactive_haie_user_44)
    response = client.get("/")

    # THEN department menu is not displayed
    content = response.content.decode()
    assert "Paramétrage" not in content

    # GIVEN an authenticated user instructor
    client.force_login(instructor_haie_user_44)
    response = client.get("/")

    # THEN department menu is displayed with only 44
    content = response.content.decode()
    assert "Paramétrage" in content

    assert 'href="/simulateur/parametrage/44"' in content
    assert 'href="/simulateur/parametrage/34"' not in content

    # GIVEN an admin user
    client.force_login(admin_user)
    response = client.get("/")

    # THEN department menu is displayed with 34 and 44
    content = response.content.decode()
    assert "Paramétrage" in content
    assert 'href="/simulateur/parametrage/44"' in content
    assert 'href="/simulateur/parametrage/34"' in content
