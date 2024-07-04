from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.tests.factories import MoulinetteConfigFactory

pytestmark = pytest.mark.django_db


HOME_TITLE = "Simulez votre projet en phase amont"
RESULT_TITLE = "Simulation réglementaire du projet"
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)
UNAVAIL = "Le simulateur EnvErgo n'est pas encore déployé dans votre département."
ADMIN_MSG = "Le simulateur n'est pas activé dans ce département"


@pytest.fixture(autouse=True)
def mock_geo_api_data():
    with patch(
        "envergo.geodata.utils.get_data_from_coords", new=Mock()
    ) as mock_geo_data:
        mock_geo_data.return_value = {
            "type": "housenumber",
            "name": "10 La Pommeraie",
            "label": "10 La Pommeraie 44140 Montbert",
            "street": "La Pommeraie",
            "postcode": "44140",
            "citycode": "44102",
            "city": "Montbert",
            "oldcitycode": None,
            "oldcity": None,
            "context": "44, Loire-Atlantique, Pays de la Loire",
            "importance": 0.47452,
            "housenumber": "10",
            "id": "44102_haa6rn_00010",
            "x": 359347.63,
            "y": 6670527.5,
            "distance": 78,
            "score": 0.9922,
            "_type": "address",
        }
        yield mock_geo_data


@pytest.fixture(autouse=True)
def mock_geo_api_commune():
    with patch(
        "envergo.geodata.utils.get_commune_from_coords", new=Mock()
    ) as mock_commune:
        mock_commune.return_value = {"code": "44102", "nom": "Montbert"}
        yield mock_commune


def test_moulinette_home(client):
    url = reverse("moulinette_home")
    res = client.get(url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()


def test_moulinette_home_with_params_redirects_to_results_page(client):
    url = reverse("moulinette_home")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)
    assert res.status_code == 302
    assert res.url.startswith("/simulateur/resultat/")


def test_moulinette_result_without_config(client):
    """When dept. contact info is not set, eval is unavailable."""

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result_non_disponible.html")


def test_moulinette_result_without_config_admin_access(client, admin_user):
    """When dept. contact info is not set, eval is unavailable, even for admins."""
    client.force_login(admin_user)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result_non_disponible.html")


def test_moulinette_result_with_deactivated_config(client):
    MoulinetteConfigFactory(is_activated=False)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result_available_soon.html")


def test_moulinette_result_with_deactivated_config_admin_access(client, admin_user):
    MoulinetteConfigFactory(is_activated=False)
    client.force_login(admin_user)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert ADMIN_MSG in res.content.decode()


def test_moulinette_result_with_activated_config(client):
    MoulinetteConfigFactory(is_activated=True)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")


def test_moulinette_result_without_params_redirects_to_home(client):
    url = reverse("moulinette_result")
    res = client.get(url)

    assert res.status_code == 302


def test_moulinette_result_form_error(client):
    url = reverse("moulinette_result")
    params = "bad_param=true"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 302
    assert res.url.endswith("/simulateur/formulaire/")


def test_moulinette_home_form_error(client):
    url = reverse("moulinette_home")
    params = "bad_param=true"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR in res.content.decode()


def test_moulinette_utm_param(client):
    url = reverse("moulinette_home")
    params = "utm_campaign=test"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()
