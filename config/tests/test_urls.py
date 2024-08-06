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
    reverse("home"),
    reverse("login"),
    reverse("password_reset"),
    reverse("contact_us"),
    reverse("accessibility"),
    reverse("stats"),
    reverse("privacy"),
    reverse("terms_of_service"),
    reverse("legal_mentions"),
    reverse("moulinette_home"),
    reverse("moulinette_result"),
]

HAIE_URLS = []

AMENAGEMENT_URLS = [
    "/avis",
    reverse("zone_map"),
    reverse("2150_debug"),
    reverse("faq"),
    reverse("news_feed"),
    reverse("geometricians"),
    reverse("parcels_export"),
    reverse("map"),
]


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_haie_can_access_pages(client):
    for url in HAIE_URLS + COMMON_URLS:
        response = client.get(url)
        assert response.status_code < 400, f"Failed for URL: {url}"

    for url in AMENAGEMENT_URLS:
        response = client.get(url)
        assert response.status_code == 404, f"Failed for URL: {url}"


def test_amenagement_can_access_pages(client):
    for url in AMENAGEMENT_URLS + COMMON_URLS:
        response = client.get(url)
        assert response.status_code < 400, f"Failed for URL: {url}"

    for url in HAIE_URLS:
        response = client.get(url)
        assert response.status_code == 404, f"Failed for URL: {url}"
