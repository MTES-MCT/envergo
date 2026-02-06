import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.geodata.conftest import france_map  # noqa: F401
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)

pytestmark = pytest.mark.django_db


def assert_url(result, url):
    res_url = result.context_data["matomo_custom_url"]
    assert res_url == f"http://testserver{url}"


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def autouse_moulinette(france_map):  # noqa
    ConfigAmenagementFactory(is_activated=True)
    RUConfigHaieFactory(is_activated=True)
    regulation = RegulationFactory(regulation="eval_env")
    CriterionFactory(
        title="Terrain d'assiette",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.TerrainAssiette",
        activation_map=france_map,
    )


def test_envergo_form(client):
    url = reverse("moulinette_form")
    res = client.get(url)
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/")


def test_envergo_prefilled_form(client):
    url = reverse("moulinette_form")
    res = client.get(f"{url}?created_surface=10000")
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/pre-rempli/")


def test_envergo_forms_optional_questions(client):
    url = reverse("moulinette_form")
    res = client.get(
        f"{url}?created_surface=10000&existing_surface=0&final_surface=10000&address=&lng=-1.66351&lat=47.06546"
    )
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/questions-complementaires/")


def test_envergo_invalid_form(client):
    url = reverse("moulinette_form")
    res = client.post(f"{url}?created_surface=10000")  # some data is missing
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/erreur-validation/")


def test_envergo_result(client):
    url = reverse("moulinette_result")
    res = client.get(
        f"{url}?created_surface=5000&existing_surface=0&final_surface=5000&address=&lng=-1.71169&lat=47.05504&surface_plancher_sup_thld=non"  # noqa
    )
    assert res.status_code == 200
    assert_url(res, "/simulateur/resultat/")


def test_envergo_result_debug(client):
    url = reverse("moulinette_result")
    res = client.get(
        f"{url}?created_surface=5000&existing_surface=0&final_surface=5000&address=&lng=-1.71169&lat=47.05504&surface_plancher_sup_thld=non&debug=oui"  # noqa
    )
    assert res.status_code == 200
    assert_url(res, "/simulateur/resultat/debug/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_haie_triage_form(client):
    url = reverse("triage")
    res = client.get(f"{url}?department=44")

    assert res.status_code == 200
    assert_url(res, "/simulateur/triage/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_haie_triage_prefilled_form(client):
    url = reverse("triage")
    res = client.get(f"{url}?department=44&element=bosquet&travaux=entretien")

    assert res.status_code == 200
    assert_url(res, "/simulateur/triage/pre-rempli/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_haie_triage_invalid(client):
    url = reverse("moulinette_result")
    res = client.get(f"{url}?department=44&element=bosquet&travaux=entretien")

    assert res.status_code == 200
    assert_url(res, "/simulateur/resultat_nspp/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_envergo_form_with_only_triage_values(client):
    url = reverse("moulinette_form")
    res = client.get(f"{url}?department=14&element=haie&travaux=destruction")
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/")


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver", ENVERGO_AMENAGEMENT_DOMAIN="otherserver"
)
def test_envergo_form_with_more_than_triage_values(client):
    url = reverse("moulinette_form")
    res = client.get(
        f"{url}?department=14&element=haie&travaux=destruction&created_surface=10000"
    )
    assert res.status_code == 200
    assert_url(res, "/simulateur/formulaire/pre-rempli/")
