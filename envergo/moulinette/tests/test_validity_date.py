import pytest

from envergo.geodata.conftest import bizous_town_center  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def n2000_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(regulation="natura2000_haie", has_perimeters=True)

    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous 2025",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            validity_date_start="2025-01-01",
            validity_date_end="2025-12-31",
            evaluator_settings={"result": "soumis"},
        ),
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous 2026",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            validity_date_start="2026-01-01",
            evaluator_settings={"result": "soumis"},
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(lat1, lng1, lat2, lng2):
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": lat1, "lng": lng1},
                    {"lat": lat2, "lng": lng2},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
                    "connexion_boisement": False,
                },
            }
        ]
    )
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": "44",
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize(
    "lat1, lng1, lat2, lng2, expected_result",
    [
        (
            43.06930871579473,
            0.4421436860179369,
            43.069162248282396,
            0.44236765047068033,
            "soumis",
        ),
    ],
)
def test_moulinette_validity_date_on_criteria(moulinette_data, expected_result):
    """Test criteria evaluated according to date in moulinette data"""
    DCConfigHaieFactory()

    # GIVEN moulinette data without date
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(moulinette_data)
    # THEN only 2026 N2000 criteria is used
    assert moulinette.get_criteria().count() == 1

    # GIVEN moulinette data with date in 2025
    moulinette_data["data"]["date"] = "2025-03-13"
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(moulinette_data)
    # THEN only 2025 N2000 criteria is used
    assert moulinette.get_criteria().count() == 1

    # GIVEN moulinette data with date in 2026
    moulinette_data["data"]["date"] = "2026-03-13"
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(moulinette_data)
    # THEN only 2025 N2000 criteria is used
    assert moulinette.get_criteria().count() == 1
