import pytest

from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.hedges.services import PlantationEvaluator
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def alignementarbres_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="alignement_arbres")

    criteria = [
        CriterionFactory(
            title="Alignement arbres > L350-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def ep_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesSimple",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def n2000_criteria(france_map, bizous_town_center):  # noqa
    regulation = RegulationFactory(regulation="natura2000_haie", has_perimeters=True)

    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=france_map,
            activation_mode="hedges_intersection",
            evaluator_settings={"result": "soumis"},
        ),
    ]
    return criteria


def test_plantation_evaluator_should_evaluate_only_activated_regulations(
    ep_criteria, alignementarbres_criteria, n2000_criteria
):
    # GIVEN two regulations, one activated, one not activated, and one without activated perimeter on a department
    DCConfigHaieFactory(regulations_available=["alignement_arbres", "natura2000_haie"])
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0695, "lng": 0.4420},
                ],
                "additionalData": {
                    "type_haie": "alignement",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
                    "connexion_boisement": False,
                    "bord_voie": True,
                },
            }
        ]
    )
    data = {
        "motif": "securite",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)

    # WHEN the plantation evaluator is created with these regulations
    evaluator = PlantationEvaluator(moulinette, moulinette_data["data"]["haies"])
    evaluator.evaluate()

    # THEN the plantation evaluator should only evaluate the activated regulation
    assert len(evaluator.conditions) == 2
    assert any(
        condition
        for condition in evaluator.conditions
        if condition.label == "Alignements d’arbres (L350-3)"
    )
    assert any(
        condition
        for condition in evaluator.conditions
        if condition.label == "Longueur de la haie plantée"
    )
