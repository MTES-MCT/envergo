from urllib.parse import urlencode

import pytest
from django.test import override_settings
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.tests.factories import ConfigHaieFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_triage_result(client):

    ConfigHaieFactory(hedge_maintenance_html="<h2>kikoo</h2>")

    url = reverse("moulinette_result")
    params = "department=44&element=haie&travaux=entretien"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "Votre projet n'est pas encore pris en compte par le simulateur" in content
    assert "<h2>kikoo</h2>" in content

    params = "department=44&element=bosquet&travaux=entretien"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "Votre projet n'est pas encore pris en compte par le simulateur" in content
    assert "<h2>kikoo</h2>" not in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
def test_debug_result(client):

    ConfigHaieFactory()

    data = {
        "profil": "autre",
        "element": "haie",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "department": "44",
        "debug": "true",
        "haies": "abdc-1234",
    }

    url = reverse("moulinette_result")
    params = urlencode(data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "haie/moulinette/result_debug.html")
