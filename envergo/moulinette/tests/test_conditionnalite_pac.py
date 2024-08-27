import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

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
    data = {
        "profil": "autre",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
    }
    for motif_choice in [
        "transfert_parcelles",
        "chemin_acces",
        "meilleur_emplacement",
        "amenagement",
        "autre",
    ]:
        for reimplantation_choice in ["remplacement", "compensation", "non"]:
            data["motif"] = motif_choice
            data["reimplantation"] = reimplantation_choice
            moulinette = MoulinetteHaie(data, data, False)
            assert moulinette.is_evaluation_available()
            assert moulinette.result == "non_soumis", (
                motif_choice,
                reimplantation_choice,
            )


def test_conditionnalite_pac_for_agri_pac():
    data = {
        "profil": "agri_pac",
        "motif": "chemin_acces",
        "reimplantation": "remplacement",
    }

    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_disponible", data

    data["lineaire_detruit"] = 5
    data["lineaire_total"] = 100
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "non_soumis_petit", data

    data["lineaire_detruit"] = 6
    data["lineaire_total"] = 100
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_remplacement"
    ), data

    data["lineaire_detruit"] = 6
    data["lineaire_total"] = 300
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "non_soumis_petit", data

    data["reimplantation"] = "compensation"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "non_soumis_petit", data

    data["lineaire_total"] = 100
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
    ), data

    data["lineaire_detruit"] = 11
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"
    ), data

    data["motif"] = "meilleur_emplacement"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "soumis_meilleur_emplacement"
    ), data

    data["motif"] = "transfert_parcelles"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_transfert_parcelles"
    ), data

    data["motif"] = "amenagement"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_disponible", data

    data["amenagement_dup"] = "oui"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data

    data["amenagement_dup"] = "non"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"
    ), data

    data["motif"] = "autre"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "non_disponible", data

    data["motif_qc"] = "aucun"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_autre", data

    data["motif_qc"] = "gestion_sanitaire"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_autre", data

    data["reimplantation"] = "non"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_autre", data

    data["motif_qc"] = "aucun"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_autre", data

    data["motif"] = "chemin_acces"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"
    ), data

    data["lineaire_detruit"] = 10
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"
    ), data

    data["motif"] = "amenagement"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"
    ), data

    data["amenagement_dup"] = "oui"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "soumis", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
    ), data

    data["motif"] = "transfert_parcelles"
    moulinette = MoulinetteHaie(data, data, False)
    assert moulinette.is_evaluation_available()
    assert moulinette.result == "interdit", data
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    ), data
