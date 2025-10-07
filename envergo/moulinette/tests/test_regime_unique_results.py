import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
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


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_moulinette_droit_constant():
    """When not in the single procedure case, returns the default result."""

    ConfigHaieFactory(single_procedure=False)
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(
                additionalData={
                    "type_haie": "alignement",
                    "bord_voie": True,
                    "sur_parcelle_pac": False,
                },
            )
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "profil": "autre",
        "motif": "securite",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "haies": hedges,
        "department": "44",
    }
    moulinette = MoulinetteHaie(data, data)
    assert moulinette.is_evaluation_available()

    # Update with this after the big moulinette refacto is merged
    # moulinette_data = {"initial": data, "data": data}
    # moulinette = MoulinetteHaie(moulinette_data)
    # assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "soumis"


def test_moulinette_result_alignement():
    """Hedges with 100% "alignement d'arbres" are outside the unique procedure."""

    ConfigHaieFactory(single_procedure=True)
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(
                additionalData={
                    "type_haie": "alignement",
                    "bord_voie": True,
                    "sur_parcelle_pac": False,
                },
            )
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "profil": "autre",
        "motif": "securite",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "haies": hedges,
        "department": "44",
    }
    moulinette = MoulinetteHaie(data, data)
    assert moulinette.is_evaluation_available()

    # Update with this after the big moulinette refacto is merged
    # moulinette_data = {"initial": data, "data": data}
    # moulinette = MoulinetteHaie(moulinette_data)
    # assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "hors_regime_unique"


def test_moulinette_result_non_alignement():
    ConfigHaieFactory(single_procedure=True)
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(
                additionalData={
                    "type_haie": "mixte",
                    "bord_voie": True,
                    "sur_parcelle_pac": False,
                },
            )
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "profil": "autre",
        "motif": "securite",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "haies": hedges,
        "department": "44",
    }
    moulinette = MoulinetteHaie(data, data)
    assert moulinette.is_evaluation_available()

    # Update with this after the big moulinette refacto is merged
    # moulinette_data = {"initial": data, "data": data}
    # moulinette = MoulinetteHaie(moulinette_data)
    # assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "declaration"


def test_moulinette_result_interdit():
    config = ConfigHaieFactory(single_procedure=False)
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(
                additionalData={
                    "type_haie": "mixte",
                    "sur_parcelle_pac": True,
                },
            )
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "profil": "autre",
        "motif": "amelioration_culture",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "transfert_parcelles": "oui",
        "meilleur_emplacement": "non",
        "haies": hedges,
        "department": "44",
        "lineaire_total": 500,
    }
    moulinette = MoulinetteHaie(data, data)
    assert moulinette.is_evaluation_available()

    # Update with this after the big moulinette refacto is merged
    # moulinette_data = {"initial": data, "data": data}
    # moulinette = MoulinetteHaie(moulinette_data)
    # assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "interdit"

    config.single_procedure = True
    config.save()
    assert moulinette.result == "interdit"
