from unittest.mock import MagicMock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=france_map,
        ),
    ]
    return criteria


def test_conditionnalite_pac_only_for_agri_pac():
    ConfigHaieFactory()
    haies = MagicMock()
    haies.length_to_remove.return_value = 10
    data = {
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "department": "44",
        "haies": haies,
    }
    for motif_choice in [
        "transfert_parcelles",
        "chemin_acces",
        "meilleur_emplacement",
        "amenagement",
        "autre",
    ]:
        for reimplantation_choice in ["remplacement", "replantation", "non"]:
            data["motif"] = motif_choice
            data["reimplantation"] = reimplantation_choice
            moulinette = MoulinetteHaie(data, data, False)
            assert moulinette.is_evaluation_available()
            assert moulinette.result == "non_soumis", (
                motif_choice,
                reimplantation_choice,
            )


def test_bcae8_small_dispense_petit():
    ConfigHaieFactory()
    data = {
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 100,
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data


def test_bcae8_small_interdit_transfert_parcelles():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 100,
        "transfert_parcelles": "oui",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    ), data


def test_bcae8_small_interdit_amelioration_culture():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 100,
        "transfert_parcelles": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_amelioration_culture"
    ), data


def test_bcae8_small_soumis_chemin_acces():
    ConfigHaieFactory()
    data = {
        "motif": "chemin_acces",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
    ), data


def test_bcae8_small_interdit_chemin_acces():
    ConfigHaieFactory()
    data = {
        "motif": "chemin_acces",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 11

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"
    ), data


def test_bcae8_small_interdit_securite():
    ConfigHaieFactory()
    data = {
        "motif": "securite",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "motif_pac": "aucun",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_securite", data


def test_bcae8_small_soumis_amenagement():
    ConfigHaieFactory()
    data = {
        "motif": "amenagement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "amenagement_dup": "oui",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data


def test_bcae8_small_interdit_amenagement():
    ConfigHaieFactory()
    data = {
        "motif": "amenagement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "amenagement_dup": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"
    ), data


def test_bcae8_small_interdit_embellissement():
    ConfigHaieFactory()
    data = {
        "motif": "embellissement",
        "reimplantation": "non",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"
    ), data


def test_bcae8_big_soumis_remplacement():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_remplacement"
    ), data


def test_bcae8_big_soumis_transfer_parcelles():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "oui",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_transfert_parcelles"
    ), data


def test_bcae8_big_interdit_amelioration_culture():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_amelioration_culture"
    ), data


def test_bcae8_big_interdit_embellissement():
    ConfigHaieFactory()
    data = {
        "motif": "embellissement",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"
    ), data


def test_bcae8_big_soumis_autre():
    ConfigHaieFactory()
    data = {
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "motif_pac": "protection_incendie",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_autre", data


def test_bcae8_big_interdit_autre():
    ConfigHaieFactory()
    data = {
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "motif_pac": "aucun",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_autre", data
