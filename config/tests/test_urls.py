import pytest
from django.contrib.sites.models import Site
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

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
    "legal_mentions",
    "privacy",
    "moulinette_form",
    "moulinette_result",
    "demo_catchment_area",
    "demo_density",
]

HAIE_URLS = [
    "triage",
]

AMENAGEMENT_URLS = [
    # "/avis",
    "terms_of_service",
    "zone_map",
    "faq",
    "news_feed",
    "geometricians",
    "parcels_export",
    "map",
]


@pytest.mark.haie
@pytest.mark.parametrize("url", COMMON_URLS + HAIE_URLS)
def test_haie_can_access_haie_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code < 400, f"Failed for URL: {url}"


@pytest.mark.haie
@pytest.mark.parametrize("url", AMENAGEMENT_URLS)
def test_haie_cannot_access_amenagement_pages(client, url):
    with pytest.raises(NoReverseMatch):
        url = reverse(url)


@pytest.mark.parametrize("url", COMMON_URLS + AMENAGEMENT_URLS)
def test_amenagement_can_access_amenagement_pages(client, url):
    url = reverse(url)
    response = client.get(url)
    assert response.status_code < 400, f"Failed for URL: {url}"


@pytest.mark.parametrize("url", HAIE_URLS)
def test_amenagement_cannot_access_haie_pages(client, url):
    with pytest.raises(NoReverseMatch):
        url = reverse(url)
