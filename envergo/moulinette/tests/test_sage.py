from urllib.parse import urlencode

import pytest
from django.urls import reverse

from envergo.moulinette.models import Criterion, MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    Perimeter,
    PerimeterFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import make_amenagement_data


@pytest.fixture(autouse=True)
def sage_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="sage", has_perimeters=True)
    perimeter = PerimeterFactory(
        name="Sage Vie Jaunay", activation_map=france_map, regulations=[regulation]
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


# ---------------------------------------------------------------------------
# SAGE criterion results
# ---------------------------------------------------------------------------


def test_result_interdit():
    """Test the default criterion result"""
    ConfigAmenagementFactory(is_activated=True)
    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.sage.result == "interdit"


def test_deactivated_regulation():
    """Test single regulation deactivation in moulinette config."""
    ConfigAmenagementFactory(is_activated=True, regulations_available=[])
    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.sage.result == "non_active"


def test_default_result_when_a_perimeter_is_found():
    Criterion.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeters.count() > 0
    assert moulinette.sage.result == "non_soumis"


def test_default_result_when_a_perimeter_is_deactivated():
    Criterion.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True

    perimeter = moulinette.sage.perimeters.all()[0]
    perimeter.is_activated = False
    perimeter.save()
    moulinette.evaluate()

    assert moulinette.sage.result == "non_disponible"


def test_default_result_when_a_perimeter_is_not_found():
    Criterion.objects.all().delete()
    Perimeter.objects.all().delete()

    ConfigAmenagementFactory(is_activated=True)
    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeters.count() == 0
    assert moulinette.sage.result == "non_concerne"


# ---------------------------------------------------------------------------
# SAGE perimeter display in views
# ---------------------------------------------------------------------------


def test_perimeter_map_display(client):
    """The perimeter map should be displayed in the result page."""
    ConfigAmenagementFactory(is_activated=True)

    url = reverse("moulinette_result")
    params = urlencode(
        {
            "created_surface": 1000,
            "final_surface": 1000,
            "lng": -1.646947,
            "lat": 47.696706,
        }
    )
    res = client.get(f"{url}?{params}")
    assert res.status_code == 200

    assert "Le projet se trouve dans le périmètre" in res.content.decode()
    assert (
        "du Schéma d'Aménagement et de Gestion des Eaux (SAGE) « Sage Vie Jaunay »"
        in res.content.decode()
    )


def test_several_perimeter_maps_display(sage_criteria, france_map, client):  # noqa
    """When several perimeters are found, they are all displayed."""
    ConfigAmenagementFactory(is_activated=True)
    PerimeterFactory(
        name="Sage Test",
        activation_map=france_map,
        regulations=[sage_criteria[0].regulation],
    )

    url = reverse("moulinette_result")
    params = urlencode(
        {
            "created_surface": 1000,
            "final_surface": 1000,
            "lng": -1.646947,
            "lat": 47.696706,
        }
    )
    res = client.get(f"{url}?{params}")
    assert res.status_code == 200

    assert (
        "Le projet se trouve dans ou à proximité de plusieurs périmètres de Schémas d’Aménagement et de Gestion des Eaux (SAGE) :"  # noqa
        in res.content.decode()
    )
    assert "« Sage Test »" in res.content.decode()


def test_several_perimeter_may_have_different_results(
    sage_criteria,
    france_map,
    client,  # noqa
):
    """When several perimeters are found, their respective results are displayed."""
    ConfigAmenagementFactory(is_activated=True)

    sage_non_disponible = PerimeterFactory(
        name="Sage Non Disponible",
        activation_map=france_map,
        regulations=[sage_criteria[0].regulation],
        is_activated=False,
    )

    sage_test = PerimeterFactory(
        name="Sage Test",
        activation_map=france_map,
        regulations=[sage_criteria[0].regulation],
    )

    CriterionFactory(
        title="Zone humide",
        regulation=sage_criteria[0].regulation,
        perimeter=sage_test,
        evaluator="envergo.moulinette.regulations.sage.ImpactZoneHumide",
        evaluator_settings={"threshold": 15000000},
        activation_map=france_map,
    )

    data = make_amenagement_data(created_surface=1000, final_surface=1000)
    moulinette = MoulinetteAmenagement(data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()
    assert moulinette.sage.results_by_perimeter == {
        sage_criteria[0].perimeter: "interdit",
        sage_test: "non_soumis",
        sage_non_disponible: "non_disponible",
    }
