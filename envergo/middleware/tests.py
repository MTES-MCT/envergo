import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@override_settings(RATELIMIT_RATE="0/s")
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
