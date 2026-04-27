import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def staff_only_criteria(france_map):  # noqa
    _config = ConfigAmenagementFactory(is_activated=True)  # noqa
    regulation = RegulationFactory(regulation="eval_env")
    criteria = [
        CriterionFactory(
            title="Aire de stationnement",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.AireDeStationnement",
            activation_map=france_map,
            is_optional=True,
            is_staff_only=True,
        ),
    ]
    return criteria


RESULT_PARAMS = (
    "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    "&evalenv_rubrique_41-activate=on"
    "&evalenv_rubrique_41-nb_emplacements=gte_50"
    "&evalenv_rubrique_41-type_stationnement=public"
)


def test_non_staff_cannot_see_staff_only_criterion_form(client):
    url = reverse("moulinette_form")
    res = client.get(url)

    assert res.status_code == 200
    assert "Aire de stationnement" not in res.content.decode()


def test_staff_can_see_staff_only_criterion_form(admin_client):
    url = reverse("moulinette_form")
    res = admin_client.get(url)

    assert res.status_code == 200
    assert "Aire de stationnement" in res.content.decode()


def test_non_staff_cannot_see_staff_only_criterion_result(client):
    url = reverse("moulinette_result")
    full_url = f"{url}?{RESULT_PARAMS}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert "Aire de stationnement" not in res.content.decode()


def test_staff_can_see_staff_only_criterion_result(admin_client):
    url = reverse("moulinette_result")
    full_url = f"{url}?{RESULT_PARAMS}"
    res = admin_client.get(full_url)

    assert res.status_code == 200
    assertTemplateUsed(res, "moulinette/result.html")
    assert "Aire de stationnement" in res.content.decode()
