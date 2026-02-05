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
    assert "&amp;numero_pacage" in result

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

    # Mixed <a> tag + other HTML (e.g. <strong>): <a> cleaned, <strong> escaped
    message = 'voici un lien <a href="https://exemple.com">https://exemple.com</a>. Et une autre <strong>balise</strong>'  # noqa: E501
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert "&lt;strong&gt;balise&lt;/strong&gt;" in result

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


def test_urlize_html_xss():
    """Test that urlize_html escapes XSS vectors."""

    # XSS: <script> tags must be escaped, not rendered
    message = "<script>alert('xss')</script>"
    result = urlize_html(message)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

    # javascript: href must not produce a clickable link
    message = "<a href=\"javascript:alert('xss')\">click me</a>"
    result = urlize_html(message)
    assert "<a " not in result

    # Multiline <script> must be escaped
    message = "<script>\nalert(1)\n</script>"
    result = urlize_html(message)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

    # <img> with onerror handler must be escaped
    message = "<img src=x onerror=alert(1)>"
    result = urlize_html(message)
    assert "<img" not in result
    assert "&lt;img src=x onerror=alert(1)&gt;" == result

    # <svg> with onload handler must be escaped
    message = "<svg onload=alert(1)>"
    result = urlize_html(message)
    assert "<svg" not in result
    assert "&lt;svg onload=alert(1)&gt;" == result

    # <iframe> must be escaped (URL inside may still be linkified)
    message = '<iframe src="https://evil.com"></iframe>'
    result = urlize_html(message)
    assert "<iframe" not in result
    assert "&lt;iframe" in result
    assert "&lt;/iframe&gt;" in result

    # <div> with event handler must be escaped
    message = '<div onmouseover="alert(1)">hover me</div>'
    result = urlize_html(message)
    assert "<div" not in result
    assert "&lt;div" in result

    # <style> tag must be escaped
    message = '<style>body{background:url("javascript:alert(1)")}</style>'
    result = urlize_html(message)
    assert "<style>" not in result
    assert "&lt;style&gt;" in result

    # Nested/broken tags must be escaped
    message = "<scr<script>ipt>alert(1)</script>"
    result = urlize_html(message)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

    # data: URI in <a> tag must not produce a clickable link
    message = '<a href="data:text/html,<script>alert(1)</script>">click</a>'
    result = urlize_html(message)
    assert "<a " not in result
    assert "&lt;script&gt;" in result

    # <a> with onclick handler — handler is stripped, only href re-urlized
    message = '<a href="https://exemple.com" onclick="alert(1)">click</a>'
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert "onclick" not in result

    # <script> inside <a> tag — <a> regex captures it, script not in output
    message = '<a href="https://exemple.com"><script>alert(1)</script></a>'
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert "<script>" not in result

    # <a> with duplicate hrefs — no javascript: link should be clickable
    message = '<a href="javascript:alert(1)" href="https://exemple.com">click</a>'
    result = urlize_html(message)
    assert 'href="javascript:' not in result

    # Mixed legitimate URL and XSS in the same message
    message = "See https://exemple.com and <script>alert(1)</script>"
    result = urlize_html(message)
    assert 'href="https://exemple.com"' in result
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_urlize_html_known_limitations():
    """Document known limitations of urlize_html.

    Django's docs warn: "If urlize is applied to text that already contains
    HTML markup, or to email addresses that contain single quotes, things
    won't work as expected. Apply this filter only to plain text."

    urlize_html receives plain text from DS messages, so these edge cases
    should be rare in practice. We document them here so regressions or
    future improvements are visible.
    """

    # Plain email (no single quote) works fine
    message = "Contact alice@example.com for info"
    result = urlize_html(message)
    assert 'href="mailto:alice@example.com"' in result

    # Email with single quote: urlize splits the address at the escaped quote.
    # "o'brien@example.com" becomes o&#x27; + a mailto link for brien@example.com
    message = "Contact o'brien@example.com for info"
    result = urlize_html(message)
    assert "o&#x27;" in result
    assert 'href="mailto:brien@example.com"' in result
    # The full address is NOT correctly linked (known limitation)
    assert 'href="mailto:o\'brien@example.com"' not in result

    # mailto: <a> tag: the regex strips the tag, leaving "mailto:alice@example.com"
    # as plain text. urlize does not re-linkify mailto: URIs.
    message = '<a href="mailto:alice@example.com">write to us</a>'
    result = urlize_html(message)
    assert "<a " not in result
    assert "mailto:alice@example.com" in result

    # Pre-escaped HTML entities get double-escaped because urlize_html
    # expects raw plain text, not pre-escaped HTML.
    message = "foo &amp; bar"
    result = urlize_html(message)
    assert "&amp;amp;" in result
