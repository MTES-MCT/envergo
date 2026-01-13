from decimal import Decimal as D

import pytest

from envergo.geodata.conftest import herault_map, loire_atlantique_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import Criterion, MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def hedges():
    h = HedgeDataFactory(
        hedges=[HedgeFactory(additionalData={"sur_parcelle_pac": False})]
    )
    return h


@pytest.fixture
def hedges_pac():
    h = HedgeDataFactory(
        hedges=[HedgeFactory(additionalData={"sur_parcelle_pac": True})]
    )
    return h


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=loire_atlantique_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_conditionnalite_pac_only_for_agri_pac():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "department": "44",
        "haies": hedges,
    }
    for motif_choice in [
        "amelioration_culture",
        "securite",
        "amenagement",
        "autre",
    ]:
        for reimplantation_choice in ["remplacement", "replantation", "non"]:
            data["motif"] = motif_choice
            data["reimplantation"] = reimplantation_choice
            moulinette_data = {
                "initial": data,
                "data": data,
            }
            moulinette = MoulinetteHaie(moulinette_data)
            assert moulinette.is_valid()
            assert moulinette.result == "non_soumis", (
                motif_choice,
                reimplantation_choice,
            )


def test_bcae8_impossible_case():
    """Impossible simulation data.

    This data configuration is prevented by the form validation.
    """
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)

    assert not moulinette.is_valid()
    assert moulinette.result == "non_disponible", data


def test_bcae8_not_activated(herault_map):  # noqa
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {
        "initial": data,
        "data": data,
    }
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data

    criterion = Criterion.objects.all()[0]
    criterion.activation_map = herault_map
    criterion.save()

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "non_disponible", data
    assert moulinette.get_criteria().count() == 0


def test_bcae8_small_dispense_petit():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {
        "initial": data,
        "data": data,
    }
    moulinette = MoulinetteHaie(moulinette_data)

    assert moulinette.is_valid()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("1")
    )


def test_bcae8_small_dispense_petit_2():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False}),
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {
        "initial": data,
        "data": data,
    }
    moulinette = MoulinetteHaie(moulinette_data)

    assert moulinette.is_valid()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data
    # GIVEN hedges to remove other than PAC, the R is computed only on PAC ones
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0.5")
    )


def test_bcae8_small_interdit_transfert_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
        "transfert_parcelles": "oui",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {
        "initial": data,
        "data": data,
    }
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    ), data


def test_bcae8_small_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {
        "initial": data,
        "data": data,
    }
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    ), data


def test_bcae8_small_soumis_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    moulinette_data = {"initial": data, "data": data}

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
    ), data


def test_bcae8_small_interdit_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=11, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"
    ), data


def test_bcae8_multi_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(length=9, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=8, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=7, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=6, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=5, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=3, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=2, additionalData={"sur_parcelle_pac": True}),
            HedgeFactory(length=1, additionalData={"sur_parcelle_pac": True}),
        ]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "chemin_acces",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
    ), data


def test_bcae8_small_interdit_securite():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "securite",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "motif_pac": "aucun",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_securite", data


def test_bcae8_small_soumis_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amenagement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "amenagement_dup": "oui",
        "batiment_exploitation": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data


def test_bcae8_small_interdit_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amenagement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "amenagement_dup": "non",
        "batiment_exploitation": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"
    ), data


def test_bcae8_small_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "embellissement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"
    ), data


def test_bcae8_big_soumis_remplacement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_remplacement"
    ), data
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_transfer_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "oui",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {"initial": data, "data": data}

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_transfert_parcelles"
    ), data
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_meilleur_emplacement_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "oui",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "soumis_meilleur_emplacement"
    ), data
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_amelioration_culture"
    ), data


def test_bcae8_big_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "embellissement",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"
    ), data


def test_bcae8_big_soumis_fosse():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "motif_pac": "rehabilitation_fosse",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_fosse", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_incendie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "motif_pac": "protection_incendie",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_incendie", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_maladie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "motif_pac": "gestion_sanitaire",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_maladie", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_interdit_autre():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "motif_pac": "aucun",
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_autre", data


def test_bcae8_batiment_exploitation():
    # GIVEN a project of amenagement on PAC land
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    data = {
        "element": "haie",
        "travaux": "destruction",
        "motif": "amenagement",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": hedges,
        "lineaire_total": 5000,
        "motif_pac": "aucun",
        "amenagement_dup": "non",
    }
    moulinette_data = {"initial": data, "data": data}

    # WHEN the batiment exploitation params is missing
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the moulinette is not valid
    assert not moulinette.is_valid()
    assert moulinette.has_missing_data()

    # WHEN the batiment exploitation params is non
    moulinette_data["data"]["batiment_exploitation"] = "non"
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is interdit
    assert moulinette.is_valid()
    assert not moulinette.has_missing_data()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"
    ), data

    # WHEN the batiment exploitation params is oui
    moulinette_data["data"]["batiment_exploitation"] = "oui"
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is soumis_amenagement
    assert moulinette.is_valid()
    assert not moulinette.has_missing_data()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data

    # EVEN on small project or without replantation
    moulinette_data["data"]["reimplantation"] = "non"
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data
