from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest

from envergo.geodata.conftest import herault_map, loire_atlantique_map  # noqa
from envergo.moulinette.models import Criterion, MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


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


def test_bcae8_impossible_case():
    """Impossible simulation data.

    This data configuration is prevented by the form validation.
    """
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
    assert moulinette.result == "non_disponible", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "non_disponible", data


def test_bcae8_not_activated(herault_map):  # noqa
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data

    criterion = Criterion.objects.all()[0]
    criterion.activation_map = herault_map
    criterion.save()

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.result == "non_disponible", data
    assert moulinette.get_criteria().count() == 0


def test_bcae8_small_dispense_petit():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 100,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4
    data["haies"].length_to_remove.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("1")
    )

    # GIVEN hedges to remove other than PAC, the R is computed only on PAC ones
    data["haies"].length_to_remove.return_value = 8
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0.5")
    )


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
        "meilleur_emplacement": "non",
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
        "meilleur_emplacement": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
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

    data["haies"].hedges_to_remove_pac.return_value = [MagicMock(length=11)]

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"
    ), data


def test_bcae8_multi_chemin_acces():
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
    data["haies"].lineaire_detruit_pac.return_value = 50

    data["haies"].hedges_to_remove_pac.return_value = [
        MagicMock(length=9),
        MagicMock(length=8),
        MagicMock(length=7),
        MagicMock(length=6),
        MagicMock(length=5),
        MagicMock(length=5),
        MagicMock(length=4),
        MagicMock(length=3),
        MagicMock(length=2),
        MagicMock(length=1),
    ]

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
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
        "meilleur_emplacement": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_remplacement"
    ), data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("1")
    )


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
        "meilleur_emplacement": "non",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_transfert_parcelles"
    ), data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("1")
    )


def test_bcae8_big_soumis_meilleur_emplacement_amelioration_culture():
    ConfigHaieFactory()
    data = {
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "transfert_parcelles": "non",
        "meilleur_emplacement": "oui",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "soumis_meilleur_emplacement"
    ), data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("1")
    )


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
        "meilleur_emplacement": "non",
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


def test_bcae8_big_soumis_fosse():
    ConfigHaieFactory()
    data = {
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "motif_pac": "rehabilitation_fosse",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_fosse", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_incendie():
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
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_incendie", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_maladie():
    ConfigHaieFactory()
    data = {
        "motif": "autre",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "department": "44",
        "haies": MagicMock(),
        "lineaire_total": 5000,
        "motif_pac": "gestion_sanitaire",
    }
    data["haies"].lineaire_detruit_pac.return_value = 4000
    data["haies"].length_to_remove.return_value = 4000

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_maladie", data
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


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
