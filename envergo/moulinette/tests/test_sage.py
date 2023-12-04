import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import Criterion, Moulinette
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    Perimeter,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def sage_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="sage", has_perimeters=True)
    PerimeterFactory(
        name="Sage Vie Jaunay", activation_map=france_map, regulation=regulation
    )
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.sage.ZoneHumideVieJaunay85",
            activation_map=france_map,
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
    }


@pytest.mark.parametrize("footprint", [1000])
def test_result_interdit(moulinette_data):
    """Test the default criterion result"""

    MoulinetteConfigFactory(is_activated=True)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.result == "interdit"


@pytest.mark.parametrize("footprint", [1000])
def test_deactivated_regulation(moulinette_data):
    """Test single regulation deactivation in moulinette config."""

    MoulinetteConfigFactory(is_activated=True, regulations_available=[])
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.result == "non_active"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_found(moulinette_data):
    Criterion.objects.all().delete()

    MoulinetteConfigFactory(is_activated=True)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeter is not None
    assert moulinette.sage.result == "non_soumis"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_deactivated(moulinette_data):
    Criterion.objects.all().delete()

    MoulinetteConfigFactory(is_activated=True)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True

    perimeter = moulinette.sage.perimeter
    perimeter.is_activated = False
    perimeter.save()
    moulinette.evaluate()

    assert moulinette.sage.perimeter is not None
    assert moulinette.sage.result == "non_disponible"


@pytest.mark.parametrize("footprint", [1000])
def test_default_result_when_a_perimeter_is_not_found(moulinette_data):
    Criterion.objects.all().delete()
    Perimeter.objects.all().delete()

    MoulinetteConfigFactory(is_activated=True)
    moulinette = Moulinette(moulinette_data, moulinette_data)
    moulinette.catalog["forbidden_wetlands_within_25m"] = True
    moulinette.evaluate()

    assert moulinette.sage.perimeter is None
    assert moulinette.sage.result == "non_concerne"
