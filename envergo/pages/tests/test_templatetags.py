import factory
import pytest
from django.test import override_settings

from envergo.geodata.tests.factories import Department34Factory
from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.pages.templatetags.utils import urlize_html

pytestmark = pytest.mark.django_db


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

    # GIVEN an authenticated user with no department
    client.force_login(haie_user)
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


def test_urlize_html():
    """Test urlize_html filter"""
    expected_result = 'voici un lien <a target="_blank" href="https://exemple.com" rel="nofollow">https://exemple.com</a>'  # noqa

    # Given a text message with a link
    message = "voici un lien https://exemple.com"
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result

    # Given a html message with a link
    message = 'voici un lien <a href="https://exemple.com" rel="nofollow">https://exemple.com</a>'
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result
