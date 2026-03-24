import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@override_settings(RATELIMIT_HARD_RATE="0/s")
@override_settings(RATELIMIT_ENABLE=True)
def test_ratelimit(client):
    # GIVEN a 0/s rate limit setting (to avoid flakyness)
    url = "/simulateur/formulaire/"

    # WHEN the user makes a POST request to the form endpoint
    response = client.post(url)
    # THEN the request should be rate limited
    assert response.status_code == 429
    assert (
        "Trop de demandes – Veuillez réessayer ultérieurement"
        in response.content.decode()
    )

    # WHEN the user makes a GET request to a moulinette endpoint
    response = client.get(url)
    # THEN the request should be rate limited
    assert response.status_code == 429
    assert (
        "Trop de demandes – Veuillez réessayer ultérieurement"
        in response.content.decode()
    )

    # WHEN the user makes a GET request to a non moulinette endpoint
    response = client.get("/")
    # THEN the request should be successful
    assert response.status_code == 200


@override_settings(RATELIMIT_HARD_RATE="0/s")
@override_settings(RATELIMIT_ENABLE=True)
def test_ratelimit_avis_get(client):
    # GIVEN a 0/s hard rate limit setting
    url = "/avis/"

    # WHEN the user makes a GET request to an avis endpoint
    response = client.get(url)
    # THEN the request should be hard rate limited
    assert response.status_code == 429


@override_settings(RATELIMIT_SOFT_RATE="0/s")
@override_settings(RATELIMIT_ENABLE=True)
def test_soft_ratelimit_get(client):
    # GIVEN a 0/s soft rate limit setting
    url = "/"

    # WHEN the user makes a GET request to any endpoint
    response = client.get(url)
    # THEN the request should be soft rate limited
    assert response.status_code == 429
