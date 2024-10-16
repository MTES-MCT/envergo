from urllib.parse import urlencode

import pytest
from django.urls import reverse

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Criterion, MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    Perimeter,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def sage_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="sage", has_perimeters=True)
    perimeter = PerimeterFactory(
        name="Sage Vie Jaunay", activation_map=france_map, regulation=regulation
    )
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.sage.ImpactZoneHumide",
            evaluator_settings={"threshold": 150},
            activation_map=france_map,
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(footprint):
    return {
        # Bizou coordinates
        "lat": 48.496195,
        "lng": 0.750409,
        "created_surface": footprint,
        "final_surface": footprint,
    }


@pytest.mark.parametrize("footprint", [1000])
def test_result_interdit(moulinette_data):
    """Test the default criterion result"""

    ConfigAmenagementFactory(is_activated=True)
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.result == "interdit"


@pytest.mark.parametrize("footprint", [1000])
def test_deactivated_regulation(moulinette_data):
    """Test single regulation deactivation in moulinette config."""

    ConfigAmenagementFactory(is_activated=True, regulations_available=[])
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.result == "non_active"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_found(moulinette_data):
    Criterion.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeters.count() > 0
    assert moulinette.sage.result == "non_soumis"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_deactivated(moulinette_data):
    Criterion.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True

    perimeter = moulinette.sage.perimeters.all()[0]
    perimeter.is_activated = False
    perimeter.save()
    moulinette.evaluate()

    assert moulinette.sage.result == "non_disponible"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_not_found(moulinette_data):
    Criterion.objects.all().delete()
    Perimeter.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeters.count() == 0
    assert moulinette.sage.result == "non_concerne"


@pytest.mark.parametrize("footprint", [1000])
def test_perimeter_map_display(moulinette_data, client):
    """The perimeter map should be displayed in the result page."""

    ConfigAmenagementFactory(is_activated=True)

    url = reverse("moulinette_result")
    params = urlencode(moulinette_data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)
    assert res.status_code == 200

    assert "Le projet se trouve dans le périmètre" in res.content.decode()
    assert (
        "du Schéma d'Aménagement et de Gestion des Eaux (SAGE) « Sage Vie Jaunay »"
        in res.content.decode()
    )


@pytest.mark.parametrize("footprint", [1000])
def test_several_perimeter_maps_display(
    moulinette_data, sage_criteria, france_map, client  # noqa
):
    """When several perimeters are found, they are all displayed."""

    ConfigAmenagementFactory(is_activated=True)
    PerimeterFactory(
        name="Sage Test",
        activation_map=france_map,
        regulation=sage_criteria[0].regulation,
    )

    url = reverse("moulinette_result")
    params = urlencode(moulinette_data)
    full_url = f"{url}?{params}"
    res = client.get(full_url)
    assert res.status_code == 200

    assert (
        "Le projet se trouve dans ou à proximité de plusieurs périmètres de Schémas d’Aménagement et de Gestion des Eaux (SAGE) :"  # noqa
        in res.content.decode()
    )
    assert "« Sage Test »" in res.content.decode()


@pytest.mark.parametrize("footprint", [1000])
def test_several_perimeter_may_have_different_results(
    moulinette_data, sage_criteria, france_map, client  # noqa
):
    """When several perimeters are found, their respective results are displayed."""

    ConfigAmenagementFactory(is_activated=True)

    sage_non_disponible = PerimeterFactory(
        name="Sage Non Disponible",
        activation_map=france_map,
        regulation=sage_criteria[0].regulation,
        is_activated=False,
    )

    sage_test = PerimeterFactory(
        name="Sage Test",
        activation_map=france_map,
        regulation=sage_criteria[0].regulation,
    )

    moulinette = MoulinetteAmenagement(moulinette_data, moulinette_data, False)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.sage.results_by_perimeter == {
        sage_criteria[0].perimeter: "interdit",
        sage_test: "non_soumis",
        sage_non_disponible: "non_disponible",
    }
