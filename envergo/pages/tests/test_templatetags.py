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

    # Plain text URL
    message = "voici un lien https://exemple.com"
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert 'target="_blank"' in result
    assert 'rel="noopener"' in result

    # URL with &numero parameter — must NOT be decoded to №
    message = "lien https://exemple.com?foo=bar&numero_pacage=012345678"
    result = urlize_html(message)
    assert "№" not in result
    assert "&numero_pacage" in result

    # Existing <a> tag: strip tag, re-urlize the href
    message = 'voici un lien <a href="https://exemple.com">https://exemple.com</a>'
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert 'target="_blank"' in result

    # Existing <a> with extra attributes (e.g. target="_blank"): strip all, re-urlize href
    message = 'voici un lien <a target="_blank" href="https://exemple.com">hello</a>.'
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert 'target="_blank"' in result

    # Two existing <a> tags: both cleaned and re-urlized
    message = 'voici un lien <a href="www.exemple.fr">coucou</a> et un deuxième lien <a href="exemple.com">hello</a>.'  # noqa: E501
    result = urlize_html(message)
    assert "www.exemple.fr" in result
    assert "exemple.com" in result
    assert result.count("<a ") == 2

    # Mixed <a> tag + other HTML (e.g. <strong>): <a> cleaned, <strong> preserved
    message = 'voici un lien <a href="https://exemple.com">https://exemple.com</a>. Et une autre <strong>balise</strong>'  # noqa: E501
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert "<strong>balise</strong>" in result

    # UTF-8 characters: accented characters must not be converted to HTML entities
    message = "voici un lien https://exemple.com avec des accents éàü"
    result = urlize_html(message)
    assert "éàü" in result
    assert "&eacute;" not in result

    # Existing <a> with bad formatting (e.g. <a    href="…" target = " _blank "): strip all, re-urlize href
    message = 'voici un lien <a  tartiflette   href= "https://exemple.com" target = "_blank">hello</a>.'
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert 'target="_blank"' in result
    assert "tartiflette" not in result
