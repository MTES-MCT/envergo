from decimal import Decimal as D

import pytest
from django.template.loader import get_template

from envergo.hedges.regulations import PacCondition
from envergo.hedges.services import PlantationEvaluator
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.models import Criterion, MoulinetteHaie
from envergo.moulinette.regulations.conditionnalitepac import (
    Bcae8BeforeRu,
    Bcae8Hru,
    Bcae8L3503,
    Bcae8Ru,
)
from envergo.moulinette.tests.factories import DCConfigHaieFactory, RUConfigHaieFactory
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_INSIDE,
    make_hedge,
    make_moulinette_haie_data,
    setup_conditionnalite_pac,
    setup_conditionnalite_pac_ru,
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
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=False)]
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


def test_bcae8_form_answers_are_shared_and_computed_data_is_not():
    """Form answers are project-wide user input, computed values belong to the evaluator."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        localisation_pac="oui",
        lineaire_total=5000,
        motif="chemin_acces",
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors

    assert moulinette.catalog["lineaire_total"] == 5000
    assert "lineaire_detruit_pac" not in moulinette.catalog

    criterion = moulinette.conditionnalite_pac.bcae8_before_ru
    assert "lineaire_total" not in criterion.get_catalog_data()
    assert criterion.get_catalog_data()["lineaire_detruit_pac"] > 0


def test_bcae8_impossible_case():
    """Impossible simulation data — prevented by form validation."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        localisation_pac="oui",
        lineaire_total=100,
        reimplantation="remplacement",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert not moulinette.is_valid()
    assert moulinette.result == "non_disponible"


def test_bcae8_not_activated(herault_map):  # noqa
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "dispense_petit"
    )

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
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "dispense_petit"
    )
    assert moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient() == D(
        "1"
    )


def test_bcae8_small_dispense_petit_2():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(length=4, additionalData__sur_parcelle_pac=True),
            HedgeFactory(length=4, additionalData__sur_parcelle_pac=False),
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "dispense_petit"
    )
    # With hedges to remove other than PAC, the R is computed only on PAC ones
    assert moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient() == D(
        "0.5"
    )


def test_bcae8_small_interdit_transfert_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_transfert_parcelles"
    )


def test_bcae8_small_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_transfert_parcelles"
    )


def test_bcae8_small_soumis_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_chemin_acces"
    )


def test_bcae8_small_interdit_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=11, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_chemin_acces"
    )


def test_bcae8_multi_chemin_acces():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[
            HedgeFactory(length=length, additionalData__sur_parcelle_pac=True)
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_chemin_acces"
    )


def test_bcae8_small_interdit_securite():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_securite"
    )


def test_bcae8_small_soumis_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_amenagement"
    )


def test_bcae8_small_interdit_amenagement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_amenagement"
    )


def test_bcae8_small_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_embellissement"
    )


# ---------------------------------------------------------------------------
# Big hedges — soumis / interdit scenarios
# ---------------------------------------------------------------------------


def test_bcae8_big_soumis_remplacement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
    )
    moulinette_data = make_moulinette_haie_data(
        hedges=hedges,
        motif="amelioration_culture",
        reimplantation="remplacement",
        localisation_pac="oui",
        lineaire_total=5000,
        transfert_parcelles="non",
        meilleur_emplacement="non",
    )
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid()
    assert moulinette.result == "soumis"
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_remplacement"
    )
    assert round(
        moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_transfer_parcelles():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_transfert_parcelles"
    )
    assert round(
        moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_soumis_meilleur_emplacement_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_meilleur_emplacement"
    )
    assert round(
        moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient(),
        1,
    ) == D("1")


def test_bcae8_big_interdit_amelioration_culture():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_amelioration_culture"
    )


def test_bcae8_big_interdit_embellissement():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_embellissement"
    )


def test_bcae8_big_soumis_fosse():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "soumis_fosse"
    assert moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient() == D(
        "0"
    )


def test_bcae8_big_soumis_incendie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "soumis_incendie"
    )
    assert moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient() == D(
        "0"
    )


def test_bcae8_big_soumis_maladie():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "soumis_maladie"
    )
    assert moulinette.conditionnalite_pac.bcae8_before_ru._evaluator.get_replantation_coefficient() == D(
        "0"
    )


def test_bcae8_big_interdit_autre():
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code == "interdit_autre"
    )


# ---------------------------------------------------------------------------
# Edge case — batiment_exploitation
# ---------------------------------------------------------------------------


def test_bcae8_batiment_exploitation():
    # GIVEN a project of amenagement on PAC land
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        hedges=[HedgeFactory(length=4000, additionalData__sur_parcelle_pac=True)]
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
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "interdit_amenagement"
    )

    # WHEN the batiment exploitation param is oui
    moulinette_data["data"]["batiment_exploitation"] = "oui"
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is soumis_amenagement
    assert moulinette.is_valid()
    assert not moulinette.has_missing_data()
    assert moulinette.result == "soumis"
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_amenagement"
    )

    # EVEN on small project or without replantation
    moulinette_data["data"]["reimplantation"] = "non"
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.result == "soumis"
    assert (
        moulinette.conditionnalite_pac.bcae8_before_ru.result_code
        == "soumis_amenagement"
    )


# ---------------------------------------------------------------------------
# Régime unique — BCAE8 is carried by the "régime unique" hedges only
# ---------------------------------------------------------------------------


class TestBcae8RegimeUnique:
    """Once the régime unique is in effect, BCAE8 only applies to RU hedges.

    HRU and L350-3 hedges are "non concerné", and RU hedges are "soumis" as
    soon as a single metre is destroyed on a PAC plot, whatever the motif.
    """

    @pytest.fixture(autouse=True)
    def conditionnalite_pac_criteria(self, loire_atlantique_map):  # noqa
        return setup_conditionnalite_pac_ru(loire_atlantique_map)

    def make_moulinette(self, hedge_data, **extra):
        RUConfigHaieFactory()
        moulinette = MoulinetteHaie(
            make_moulinette_haie_data(hedge_data=hedge_data, **extra)
        )
        assert moulinette.is_valid(), moulinette.form_errors
        return moulinette

    def test_ru_hedge_on_pac_plot_is_soumis(self):
        moulinette = self.make_moulinette(
            [make_hedge(type_haie="mixte", sur_parcelle_pac=True)],
            localisation_pac="oui",
        )
        assert moulinette.conditionnalite_pac.ru__bcae8.result_code == "soumis"
        assert moulinette.conditionnalite_pac.ru__bcae8.result == "soumis"
        assert moulinette.conditionnalite_pac.result == "soumis"

    def test_ru_hedge_outside_pac_plot_is_non_concerne(self):
        moulinette = self.make_moulinette(
            [make_hedge(type_haie="mixte", sur_parcelle_pac=False)]
        )
        assert moulinette.conditionnalite_pac.ru__bcae8.result_code == "non_concerne"
        assert moulinette.conditionnalite_pac.result == "non_concerne"

    def test_hru_hedge_is_never_concerned(self):
        moulinette = self.make_moulinette(
            [
                make_hedge(
                    type_haie="alignement", bord_voie=False, sur_parcelle_pac=True
                )
            ],
            localisation_pac="oui",
        )
        assert moulinette.conditionnalite_pac.hru__bcae8.result_code == "non_concerne"
        assert moulinette.conditionnalite_pac.result == "non_concerne"

    def test_l350_3_hedge_is_never_concerned(self):
        moulinette = self.make_moulinette(
            [make_hedge(type_haie="alignement", bord_voie=True, sur_parcelle_pac=True)],
            localisation_pac="oui",
        )
        assert (
            moulinette.conditionnalite_pac.l350_3__bcae8.result_code == "non_concerne"
        )
        assert moulinette.conditionnalite_pac.result == "non_concerne"

    def test_replantation_coefficient_is_the_pac_share(self):
        """R is the share of the destroyed RU linear that sits on a PAC plot."""
        moulinette = self.make_moulinette(
            [
                make_hedge(
                    hedge_id="D1",
                    type_haie="mixte",
                    sur_parcelle_pac=True,
                    coords=COORDS_BIZOUS_INSIDE,
                ),
                make_hedge(
                    hedge_id="D2",
                    type_haie="mixte",
                    sur_parcelle_pac=False,
                    coords=COORDS_BIZOUS_INSIDE,
                ),
            ],
            localisation_pac="oui",
        )
        evaluator = moulinette.conditionnalite_pac.ru__bcae8._evaluator
        assert evaluator.get_replantation_coefficient() == pytest.approx(0.5)

    def test_replantation_coefficient_without_pac_destruction(self):
        """Destroying nothing on a PAC plot asks for no replantation."""
        moulinette = self.make_moulinette(
            [make_hedge(type_haie="mixte", sur_parcelle_pac=False)]
        )
        evaluator = moulinette.conditionnalite_pac.ru__bcae8._evaluator
        assert evaluator.get_replantation_coefficient() == 0

    def test_pac_condition_is_listed_when_pac_hedges_are_destroyed(self):
        """The plantation evaluation exposes the "maintien des haies PAC" condition."""
        moulinette = self.make_moulinette(
            [
                make_hedge(hedge_id="D1", type_haie="mixte", sur_parcelle_pac=True),
                make_hedge(
                    hedge_id="P1",
                    hedge_type="TO_PLANT",
                    type_haie="mixte",
                    sur_parcelle_pac=False,
                ),
            ],
            localisation_pac="oui",
        )
        evaluator = PlantationEvaluator(moulinette, moulinette.catalog["haies"])
        evaluator.evaluate()

        pac_conditions = [
            c for c in evaluator.conditions if isinstance(c, PacCondition)
        ]
        assert len(pac_conditions) == 1
        condition = pac_conditions[0]
        # Nothing was planted on a PAC plot, so the condition is not met.
        assert not condition.result
        assert condition.must_display()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
# A missing criterion template is rendered as an empty string, so the only way
# to catch a base_slug / template path mismatch is to assert it explicitly.


@pytest.mark.parametrize(
    "evaluator, result_codes",
    [
        (Bcae8BeforeRu, sorted(Bcae8BeforeRu.RESULT_MATRIX)),
        (Bcae8Hru, ["non_concerne"]),
        (Bcae8L3503, ["non_concerne"]),
        (Bcae8Ru, sorted(set(Bcae8Ru.CODE_MATRIX.values()))),
    ],
)
def test_every_result_code_has_a_template(evaluator, result_codes):
    for result_code in result_codes:
        template_name = (
            f"moulinette/conditionnalite_pac/{evaluator.category.name}/"
            f"{evaluator.base_slug}_{result_code}.html"
        )
        get_template(template_name)
