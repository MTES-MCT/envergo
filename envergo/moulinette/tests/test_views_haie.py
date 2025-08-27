from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.analytics.models import Event
from envergo.geodata.conftest import loire_atlantique_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


HOME_TITLE = "Projet de destruction de haies ou alignements d'arbres"
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)


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
def test_triage(client):
    ConfigHaieFactory(department_doctrine_html="<h2>Doctrine du département</h2>")

    url = reverse("triage")
    params = "department=44"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "<h2>Doctrine du département</h2>" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_triage_result(client):

    ConfigHaieFactory(
        department_doctrine_html="<h2>Doctrine du département</h2>",
        hedge_maintenance_html="<h2>kikoo</h2>",
    )

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

    params = "department=44&element=haie&travaux=destruction"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert "<h2>Doctrine du département</h2>" in content


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


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_result_p_view_non_soumis_with_r_gt_0(client):
    ConfigHaieFactory()
    hedge_lt5m = HedgeFactory(
        latLngs=[
            {"lat": 49.37830760743562, "lng": 0.10241746902465822},
            {"lat": 49.37828490574639, "lng": 0.10244965553283693},
        ]
    )
    hedges = HedgeDataFactory(hedges=[hedge_lt5m])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges.id,
        "lineaire_total": 20000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    url = reverse("moulinette_result")
    query = urlencode(data)
    res = client.get(f"{url}?{query}")

    assert "Déposer une demande sans plantation" not in res.content.decode()


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_moulinette_post_form_error(client):
    ConfigHaieFactory()
    url = reverse("moulinette_home")
    data = {"foo": "bar"}
    res = client.post(f"{url}?department=44&element=haie&travaux=destruction", data)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert FORM_ERROR in res.content.decode()
    error_event = Event.objects.filter(category="erreur", event="formulaire-simu").get()
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "haies": [
            "Aucune haie n’a été saisie. Cliquez sur le bouton ci-dessus pour\n"
            "            localiser les haies à détruire."
        ],
        "localisation_pac": ["Ce champ est obligatoire."],
        "motif": ["Ce champ est obligatoire."],
        "reimplantation": ["Ce champ est obligatoire."],
    }
    assert "data" in error_event.metadata
    assert error_event.metadata["data"] == data
