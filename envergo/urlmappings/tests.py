import pytest
from django.urls import reverse

from envergo.urlmappings.models import UrlMapping

pytestmark = pytest.mark.django_db

CREATE_URL = reverse("urlmapping_create")

AMENAGEMENT_DOMAIN = "amenagement.test.gouv.fr"
HAIE_DOMAIN = "haie.test.gouv.fr"


@pytest.fixture(autouse=True)
def urlmapping_domains(settings):
    settings.ENVERGO_AMENAGEMENT_DOMAIN = AMENAGEMENT_DOMAIN
    settings.ENVERGO_HAIE_DOMAIN = HAIE_DOMAIN


def test_create_mapping_with_amenagement_domain(client):
    url = f"https://{AMENAGEMENT_DOMAIN}/moulinette/resultat/?lng=-1.5&lat=47.2"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 201
    assert UrlMapping.objects.count() == 1


def test_create_mapping_with_haie_domain(client):
    url = f"https://{HAIE_DOMAIN}/haie/resultat/?element=haie&lng=-1.5&lat=47.2"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 201
    assert UrlMapping.objects.count() == 1


def test_create_mapping_with_http_is_accepted(client):
    """Local dev uses http — both schemes must be allowed."""
    url = f"http://{AMENAGEMENT_DOMAIN}/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 201
    assert UrlMapping.objects.count() == 1


def test_create_mapping_with_port_is_accepted(client):
    """Local dev uses non-standard ports."""
    url = f"http://{AMENAGEMENT_DOMAIN}:8000/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 201
    assert UrlMapping.objects.count() == 1


def test_external_domain_is_rejected(client):
    url = "https://evil.example.com/spam"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_subdomain_of_allowed_domain_is_rejected(client):
    url = f"https://evil.{AMENAGEMENT_DOMAIN}/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_domain_lookalike_is_rejected(client):
    """A domain containing an allowed domain as a suffix must not pass."""
    url = f"https://not-{AMENAGEMENT_DOMAIN}/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_allowed_domain_in_path_is_rejected(client):
    """The allowed domain appearing only in the path must not bypass validation."""
    url = f"https://evil.example.com/{AMENAGEMENT_DOMAIN}/moulinette/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_empty_url_is_rejected(client):
    res = client.post(CREATE_URL, {"url": ""})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_missing_url_is_rejected(client):
    res = client.post(CREATE_URL, {})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_userinfo_trick_is_rejected(client):
    """An attacker can craft a URL with an allowed domain in the userinfo part."""
    url = f"https://{AMENAGEMENT_DOMAIN}@evil.example.com/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 400
    assert UrlMapping.objects.count() == 0


def test_uppercase_hostname_is_accepted(client):
    """Hostnames are case-insensitive per RFC — uppercase must be accepted."""
    domain = AMENAGEMENT_DOMAIN.upper()
    url = f"https://{domain}/moulinette/resultat/"
    res = client.post(CREATE_URL, {"url": url})

    assert res.status_code == 201
    assert UrlMapping.objects.count() == 1
