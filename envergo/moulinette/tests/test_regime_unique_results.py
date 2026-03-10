import pytest

from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)


@pytest.fixture(autouse=True)
def alignementarbres_criteria(france_map):  # noqa
    regulation = RegulationFactory(
        regulation="alignement_arbres",
        evaluator="envergo.moulinette.regulations.alignementarbres.AlignementArbresRegulation",
    )

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
    regulation = RegulationFactory(
        regulation="conditionnalite_pac",
        evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8Regulation",
    )
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


@pytest.fixture
def ep_criteria(france_map):  # noqa
    regulation = RegulationFactory(
        regulation="ep", evaluator="envergo.moulinette.regulations.ep.EPRegulation"
    )
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_moulinette_droit_constant():
    """When not in the single procedure case, returns the default result."""

    DCConfigHaieFactory(single_procedure=False)
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
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "soumis"


def test_moulinette_result_alignement():
    """Hedges with 100% "alignement d'arbres" are outside the unique procedure."""

    DCConfigHaieFactory(
        single_procedure=True,
        single_procedure_settings={
            "coeff_compensation": {
                "mixte": 1.5,
                "degradee": 1.5,
                "arbustive": 1.5,
                "buissonnante": 1.5,
            }
        },
    )
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
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "hors_regime_unique"


def test_moulinette_result_non_alignement():
    DCConfigHaieFactory(
        single_procedure=True,
        single_procedure_settings={
            "coeff_compensation": {
                "mixte": 1.5,
                "degradee": 1.5,
                "arbustive": 1.5,
                "buissonnante": 1.5,
            }
        },
    )
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
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.conditionnalite_pac.result == "non_soumis"
    assert moulinette.alignement_arbres.result == "non_soumis"
    assert moulinette.result == "declaration"


def test_moulinette_result_interdit():
    config = DCConfigHaieFactory(single_procedure=False)
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
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.result == "interdit"

    config.single_procedure = True
    config.single_procedure_settings = {
        "coeff_compensation": {
            "mixte": 1.5,
            "degradee": 1.5,
            "arbustive": 1.5,
            "buissonnante": 1.5,
        }
    }
    config.save()
    assert moulinette.result == "interdit"


def test_moulinette_result_autorisation(ep_criteria):
    DCConfigHaieFactory(
        single_procedure=True,
        single_procedure_settings={
            "coeff_compensation": {
                "mixte": 1.5,
                "degradee": 1.5,
                "arbustive": 1.5,
                "buissonnante": 1.5,
            }
        },
    )
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(
                additionalData={
                    "type_haie": "mixte",
                    "sur_parcelle_pac": False,
                    "mode_destruction": "coupe_a_blanc",
                },
            )
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "transfert_parcelles": "oui",
        "meilleur_emplacement": "non",
        "haies": hedges,
        "department": "44",
        "lineaire_total": 500,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()

    assert moulinette.ep.ep_aisne.result == "derogation_simplifiee"
    assert moulinette.result == "autorisation"
