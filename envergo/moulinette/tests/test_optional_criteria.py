import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def evalenv_criteria(france_map):  # noqa
    _config = MoulinetteConfigFactory(is_activated=True)  # noqa
    regulation = RegulationFactory(regulation="eval_env")
    criteria = [
        CriterionFactory(
            title="Aire de stationnement",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.AireDeStationnement",
            activation_map=france_map,
            is_optional=True,
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.4961953,
        "lng": 0.7504093,
        "existing_surface": 0,
        "created_surface": footprint,
        "final_surface": footprint,
        "emprise": 20000,
        "zone_u": "oui",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
    }


# ETQ Admin, je peux voir l'option d'activer un critère optionnel
def test_edition_redirection_from_result_admin_see_optional_criterion_additional_question(
    admin_client,
):
    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&edit=true"
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/home.html")

    # The question exists in the sidebar
    assert "Rubrique 41 : aires de stationnement" in res.content.decode()

    # The criterion is not activated
    assert "Aire de stationnement" not in res.content.decode()

    # The form is not validated, no error message is shown
    assert "error-text-evalenv_rubrique_41-soumis" not in res.content.decode()


# ETQ admin, je peux voir les questions optionnelles dès l'accueil du simulateur
def test_optional_questions_appear_on_moulinette_home(admin_client):
    url = reverse("moulinette_home")
    res = admin_client.get(url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/home.html")

    # The question exists in the sidebar
    assert "Rubrique 41 : aires de stationnement" in res.content.decode()


# ETQ User, je ne peux pas voir l'option d'activer un critère optionnel
def test_users_cannot_see_optional_criterion_additional_question(client):
    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    # The question does not exist in the sidebar
    assert "Rubrique 41 : aires de stationnement" not in res.content.decode()

    # The criterion is  not activated
    assert "Aire de stationnement" not in res.content.decode()


# ETQ Admin, je peux consulter une simulation avec un critère optionnel
def test_admin_see_optional_criterion_result(admin_client):
    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=gte_50&evalenv_rubrique_41-type_stationnement=public"  # noqa
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")

    # The criterion is activated
    assert "Aire de stationnement" in res.content.decode()


# ETQ User, je ne peux pas consulter une simulation avec un critère optionnel
def test_users_cannot_see_optional_criterion_results(client):
    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&evalenv_rubrique_41-activate=on&evalenv_rubrique_41-nb_emplacements=gte_50"  # noqa
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 302
    assert "evalenv_rubrique_41_soumis" not in res["Location"]


def test_optional_criterion_activation(admin_client):
    """If the form is activated, fields become required."""

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&evalenv_rubrique_41-activate=on"
    full_url = f"{url}?{params}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/home.html")
