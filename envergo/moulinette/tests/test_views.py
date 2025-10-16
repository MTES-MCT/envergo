import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.analytics.models import Event
from envergo.geodata.conftest import france_map  # noqa: F401
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


HOME_TITLE = "Simulez votre projet en phase amont"
RESULT_TITLE = "Simulation réglementaire du projet"
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)
UNAVAIL = "Le simulateur Envergo n'est pas encore déployé dans votre département."
ADMIN_MSG = "Le simulateur n'est pas activé dans ce département"


def test_moulinette_home(client):
    url = reverse("moulinette_form")
    res = client.get(url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()


def test_moulinette_form_with_params_displays_the_form(client):
    url = reverse("moulinette_form")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)
    assert res.status_code == 200
    assert (
        '<input type="text" name="created_surface" value="500"' in res.content.decode()
    )


def test_moulinette_result_without_config(client):
    """When dept. contact info is not set, eval is unavailable."""

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "amenagement/moulinette/result_non_disponible.html")


def test_moulinette_result_without_config_admin_access(client, admin_user):
    """When dept. contact info is not set, eval is unavailable, even for admins."""
    client.force_login(admin_user)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "amenagement/moulinette/result_non_disponible.html")


def test_moulinette_result_with_deactivated_config(client):
    ConfigAmenagementFactory(is_activated=False)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result_available_soon.html")


def test_moulinette_result_with_deactivated_config_admin_access(client, admin_user):
    ConfigAmenagementFactory(is_activated=False)
    client.force_login(admin_user)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert ADMIN_MSG in res.content.decode()


def test_moulinette_result_with_activated_config(client):
    ConfigAmenagementFactory(is_activated=True)

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


def test_moulinette_result_mtm_keywords_are_not_bad_params(client):
    """Analytics params are not cleaned from the result url."""
    ConfigAmenagementFactory(is_activated=True)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&mtm_campaign=test"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")


def test_moulinette_result_debug_page(client):
    """Debug page
    But no activation map is triggered / no criterion, no perimeter, no zone
    """

    url = reverse("moulinette_result")
    params = (
        "created_surface=2000&final_surface=2000&lng=-1.54394&lat=47.21381&debug=true"
    )
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "amenagement/moulinette/result_debug.html")


def test_moulinette_result_custom_matomo_tracking_url(client):
    ConfigAmenagementFactory(is_activated=True)

    url = reverse("moulinette_result")
    params = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381&mtm_campaign=test"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    content = res.content.decode()
    assert (
        'var MATOMO_CUSTOM_URL = "http://testserver/simulateur/resultat/?mtm_campaign=test";'
        in content
    )


def test_moulinette_post_form_error(client):
    url = reverse("moulinette_form")
    data = {"lng": "-1.54394", "lat": "47.21381"}
    res = client.post(url, data)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR in res.content.decode()
    error_event = Event.objects.filter(category="erreur", event="formulaire-simu").get()
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "created_surface": [
            {"code": "required", "message": "Ce champ est obligatoire."}
        ],
        "final_surface": [{"code": "required", "message": "Ce champ est obligatoire"}],
    }
    assert "data" in error_event.metadata
    assert error_event.metadata["data"] == data


def test_moulinette_post_qc_form_error(client, france_map):  # noqa: F811
    # GIVEN a moulinette configured with one criterion requiring complementary questions
    ConfigAmenagementFactory(is_activated=True)
    regulation = RegulationFactory(regulation="eval_env")
    CriterionFactory(
        title="Terrain d'assiette",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.TerrainAssiette",
        activation_map=france_map,
    )
    url = reverse("moulinette_form")
    data = {
        "lng": "-1.54394",
        "lat": "47.21381",
        "created_surface": 45000,
        "final_surface": 45000,
    }

    # WHEN I post a form without answering the complementary questions
    res = client.post(url, data, follow=True)

    # THEN I am redirect to the form with the complementary questions BUT there is no event created
    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert "Questions complémentaires" in res.content.decode()
    assert Event.objects.filter(category="erreur", event="formulaire-simu").count() == 0

    # WHEN I post a form with invalid value to the complementary questions
    data = {
        "lng": "-1.54394",
        "lat": "47.21381",
        "created_surface": 45000,
        "final_surface": 45000,
        "terrain_assiette": "azerty",
    }
    res = client.post(url, data, follow=True)

    # THEN I get an error message and an event is created
    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert "↑\n      Saisissez un nombre entier.\n      ↑" in res.content.decode()

    error_event = Event.objects.filter(category="erreur", event="formulaire-simu").get()
    assert "errors" in error_event.metadata
    assert error_event.metadata["errors"] == {
        "operation_amenagement": [
            {"code": "required", "message": "Ce champ est obligatoire."}
        ],
        "terrain_assiette": [
            {"code": "invalid", "message": "Saisissez un nombre entier."}
        ],
    }
    assert "data" in error_event.metadata


def test_moulinette_utm_param(client):
    url = reverse("moulinette_form")
    params = "utm_campaign=test"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()


def test_moulinette_form_surface_field(client):
    ConfigAmenagementFactory()

    # WHEN I post a form with inconsistent surfaces
    url = reverse("moulinette_form")
    data = {
        "created_surface": 1500,
        "final_surface": 500,
        "lng": -1.54394,
        "lat": 47.21381,
    }
    res = client.post(url, data, follow=True)
    # THEN I should get an error message
    assert res.status_code == 200

    assert (
        "La surface impactée totale doit être au moins égale à celle des nouveaux impacts"
        in res.content.decode()
    )

    # WHEN I post a form with inconsistent existing_surface
    data = {
        "created_surface": 1500,
        "final_surface": 1500,
        "existing_surface": -500,
        "lng": -1.54394,
        "lat": 47.21381,
    }
    res = client.post(url, data)
    # THEN it should override existing_surface
    assert res.status_code == 302
    assert (
        res.url
        == "/simulateur/resultat/?created_surface=1500&existing_surface=0&final_surface=1500&address=&lng=-1.54394&lat=47.21381"
    )
