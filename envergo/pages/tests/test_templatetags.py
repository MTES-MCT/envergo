import factory
import pytest
from django.test import override_settings

from envergo.geodata.tests.factories import Department34Factory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.pages.templatetags.utils import urlize_html

pytestmark = pytest.mark.django_db


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_petition_department_list(
    inactive_haie_user_44, haie_instructor_44, haie_user, admin_user, client, site
):

    DCConfigHaieFactory()
    DCConfigHaieFactory(department=factory.SubFactory(Department34Factory))

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
    client.force_login(haie_instructor_44)
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

    # Given a text message with a link
    message = "voici un lien https://exemple.com"
    expected_result = 'voici un lien <a target="_blank" rel="noopener" href="https://exemple.com" rel="nofollow">https://exemple.com</a>'  # noqa: E501
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result

    # Given a html message with a link and another tag
    message = 'voici un lien <a href="https://exemple.com">https://exemple.com</a>. Et une autre <strong>balise</strong>'  # noqa: E501
    expected_result = 'voici un lien <a target="_blank" rel="noopener" href="https://exemple.com" rel="nofollow">https://exemple.com</a>. Et une autre <strong>balise</strong>'  # noqa: E501
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result

    # Given a html message with two links
    message = 'voici un lien <a href="www.exemple.fr">coucou</a> et un deuxième lien <a href="exemple.com">hello</a>.'
    expected_result = 'voici un lien <a target="_blank" rel="noopener" href="http://www.exemple.fr" rel="nofollow">www.exemple.fr</a> et un deuxième lien <a target="_blank" rel="noopener" href="http://exemple.com" rel="nofollow">exemple.com</a>.'  # noqa: E501
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result

    # Given a html message with a links with target="_blank"
    message = 'voici un lien <a target="_blank" href="https://exemple.com">hello</a>.'
    expected_result = 'voici un lien <a target="_blank" rel="noopener" href="https://exemple.com" rel="nofollow">https://exemple.com</a>.'  # noqa: E501
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result
