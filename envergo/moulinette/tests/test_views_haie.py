from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.geodata.conftest import loire_atlantique_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=False)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=loire_atlantique_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
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
    """WIP: Test for debug page.
    Missing fixtures criteria ep and pac for MoulinetteHaie"""

    ConfigHaieFactory()
    haies = HedgeDataFactory()

    data = {
        "profil": "autre",
        "element": "haie",
        "motif": "amelioration_ecologique",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "travaux": "destruction",
        "haies": str(haies.id),
        "department": "44",
        "debug": "true",
    }
    url = reverse("moulinette_result")
    params = urlencode(data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    # assertTemplateUsed(res, "haie/moulinette/result_debug.html")


@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
@patch("envergo.hedges.services.get_replantation_coefficient")
def test_result_p_view_with_R_gt_0(mock_R, client):
    ConfigHaieFactory()
    hedges = HedgeDataFactory()
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    mock_R.return_value = 1.0
    res = client.get(f"{url}?{query}")

    assert "Déposer une demande sans plantation" not in res.content.decode()


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
@patch("envergo.hedges.services.get_replantation_coefficient")
def test_result_p_view_with_R_eq_0(mock_R, client):
    ConfigHaieFactory()
    hedges = HedgeDataFactory()
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    mock_R.return_value = 0.0
    res = client.get(f"{url}?{query}")

    # R should be 0
    assert "Déposer une demande sans plantation" in res.content.decode()
