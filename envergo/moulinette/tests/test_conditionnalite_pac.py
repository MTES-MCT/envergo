from decimal import Decimal as D

import pytest

from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import Criterion, MoulinetteHaie
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.moulinette.tests.utils import (
    make_moulinette_haie_data,
    setup_conditionnalite_pac,
)


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    return setup_conditionnalite_pac(loire_atlantique_map)


# ---------------------------------------------------------------------------
# Non-PAC profiles — should never be "soumis"
# ---------------------------------------------------------------------------


def test_conditionnalite_pac_only_for_agri_pac():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False})]
    )
    for motif_choice in [
        "amelioration_culture",
        "securite",
        "amenagement",
        "autre",
    ]:
        for reimplantation_choice in ["remplacement", "replantation", "non"]:
            moulinette_data = make_moulinette_haie_data(
                hedges=hedges,
                motif=motif_choice,
                reimplantation=reimplantation_choice,
            )
            moulinette = MoulinetteHaie(moulinette_data)
            assert moulinette.is_valid()
            assert moulinette.result == "non_soumis", (
                motif_choice,
                reimplantation_choice,
            )


def test_bcae8_impossible_case():
    """Impossible simulation data — prevented by form validation."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        localisation_pac="oui",
        lineaire_total=100,
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert not moulinette.is_valid()
    assert moulinette.result == "non_disponible"


def test_bcae8_not_activated(herault_map):  # noqa
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        localisation_pac="oui",
        lineaire_total=100,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "non_soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit"

    criterion = Criterion.objects.all()[0]
    criterion.activation_map = herault_map
    criterion.save()

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "non_disponible"
    assert moulinette.get_criteria().count() == 0


# ---------------------------------------------------------------------------
# Small hedges — dispense / interdit scenarios
# ---------------------------------------------------------------------------


def test_bcae8_small_dispense_petit():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        localisation_pac="oui",
        lineaire_total=100,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "non_soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit"
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
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        localisation_pac="oui",
        lineaire_total=100,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "non_soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "dispense_petit"
    # With hedges to remove other than PAC, the R is computed only on PAC ones
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0.5")
    )


def test_bcae8_small_interdit_transfert_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=100,
        transfert_parcelles="oui",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    )


def test_bcae8_small_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=100,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_transfert_parcelles"
    )


def test_bcae8_small_soumis_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="chemin_acces",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"


def test_bcae8_small_interdit_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=11, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="chemin_acces",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_chemin_acces"


def test_bcae8_multi_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(length=length, additionalData={"sur_parcelle_pac": True})
            for length in [9, 8, 7, 6, 5, 4, 3, 2, 1]
        ]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="chemin_acces",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_chemin_acces"


def test_bcae8_small_interdit_securite():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="securite",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
        motif_pac="aucun",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_securite"


def test_bcae8_small_soumis_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amenagement",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        amenagement_dup="oui",
        batiment_exploitation="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"


def test_bcae8_small_interdit_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amenagement",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
        amenagement_dup="non",
        batiment_exploitation="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"


def test_bcae8_small_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="embellissement",
        reimplantation="non",
        localisation_pac="oui",
        lineaire_total=5000,
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"


# ---------------------------------------------------------------------------
# Big hedges — soumis / interdit scenarios
# ---------------------------------------------------------------------------


def test_bcae8_big_soumis_remplacement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_remplacement"
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_transfer_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="oui",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code == "soumis_transfert_parcelles"
    )
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_meilleur_emplacement_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
        meilleur_emplacement="oui",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "soumis_meilleur_emplacement"
    )
    assert round(
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert (
        moulinette.conditionnalite_pac.bcae8.result_code
        == "interdit_amelioration_culture"
    )


def test_bcae8_big_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="embellissement",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_embellissement"


def test_bcae8_big_soumis_fosse():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        motif_pac="rehabilitation_fosse",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_fosse"
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_incendie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        motif_pac="protection_incendie",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_incendie"
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_soumis_maladie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        motif_pac="gestion_sanitaire",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_maladie"
    assert (
        moulinette.conditionnalite_pac.bcae8._evaluator.get_replantation_coefficient()
        == D("0")
    )


def test_bcae8_big_interdit_autre():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="autre",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        motif_pac="aucun",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_autre"


# ---------------------------------------------------------------------------
# Edge case — batiment_exploitation
# ---------------------------------------------------------------------------


def test_bcae8_batiment_exploitation():
    # GIVEN a project of amenagement on PAC land
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData={"sur_parcelle_pac": True})]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amenagement",
        reimplantation="replantation",
        localisation_pac="oui",
        lineaire_total=5000,
        motif_pac="aucun",
        amenagement_dup="non",
    )

    # WHEN the batiment exploitation param is missing
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the moulinette is not valid
    assert not moulinette.is_valid()
    assert moulinette.has_missing_data()

    # WHEN the batiment exploitation param is non
    moulinette_data["data"]["batiment_exploitation"] = "non"
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is interdit
    assert moulinette.is_valid()
    assert not moulinette.has_missing_data()
    assert moulinette.result == "interdit"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "interdit_amenagement"

    # WHEN the batiment exploitation param is oui
    moulinette_data["data"]["batiment_exploitation"] = "oui"
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is soumis_amenagement
    assert moulinette.is_valid()
    assert not moulinette.has_missing_data()
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"

    # EVEN on small project or without replantation
    moulinette_data["data"]["reimplantation"] = "non"
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "soumis"
    assert moulinette.conditionnalite_pac.bcae8.result_code == "soumis_amenagement"
