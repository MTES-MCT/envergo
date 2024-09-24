import pytest
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def site() -> Site:
    return SiteFactory()


COMMON_URLS = [
    "home",
    "login",
    "password_reset",
    "contact_us",
    "accessibility",
    "stats",
    "privacy",
    "terms_of_service",
    "legal_mentions",
    "moulinette_home",
    "moulinette_result",
]

HAIE_URLS = [
    "triage",
    "triage_result",
]

AMENAGEMENT_URLS = [
    # "/avis",
    "zone_map",
    "2150_debug",
    "faq",
    "news_feed",
    "geometricians",
    "parcels_export",
    "map",
]


@pytest.mark.urls("config.urls_haie")
@pytest.mark.parametrize("url", COMMON_URLS + HAIE_URLS)
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_can_access_haie_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code < 400, f"Failed for URL: {url}"


@pytest.mark.urls("config.urls_haie")
@pytest.mark.parametrize("url", AMENAGEMENT_URLS)
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_cannot_access_amenagement_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code == 404, f"Failed for URL: {url}"


@pytest.mark.parametrize("url", COMMON_URLS + AMENAGEMENT_URLS)
def test_amenagement_can_access_amenagement_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code < 400, f"Failed for URL: {url}"


@pytest.mark.parametrize("url", HAIE_URLS)
def test_amenagement_cannot_access_haie_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code == 404, f"Failed for URL: {url}"
