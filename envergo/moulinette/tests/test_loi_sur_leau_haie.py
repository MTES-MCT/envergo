import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.regulations.loi_sur_leau_haie import LoiSurLeauHaieRuForm
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data


@pytest.fixture(autouse=True)
def loi_sur_leau_haie_criteria(france_map):  # noqa: F811
    regulation = RegulationFactory(
        regulation="loi_sur_leau_haie",
        evaluator="envergo.moulinette.regulations.loi_sur_leau_haie.LoiSurLeauHaieRegulation",
    )
    CriterionFactory(
        title="Loi sur l'eau Haie HRU",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.loi_sur_leau_haie.LoiSurLeauHaieHru",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    CriterionFactory(
        title="Loi sur l'eau Haie L350-3",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.loi_sur_leau_haie.LoiSurLeauHaieL3503",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    CriterionFactory(
        title="Loi sur l'eau Haie RU",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.loi_sur_leau_haie.LoiSurLeauHaieRu",
        activation_map=france_map,
        activation_mode="department_centroid",
    )


@pytest.mark.parametrize(
    "ripisylve, expected_result",
    [
        (True, "a_verifier"),
        (False, "non_concerne"),
    ],
)
def test_hru(ripisylve, expected_result):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="alignement", bord_voie=False, ripisylve=ripisylve)
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.loi_sur_leau_haie.hru__loi_sur_leau_haie.result == expected_result


@pytest.mark.parametrize(
    "ripisylve, expected_result",
    [
        (True, "a_verifier"),
        (False, "non_concerne"),
    ],
)
def test_l350_3(ripisylve, expected_result):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="alignement", bord_voie=True, ripisylve=ripisylve)
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert (
        moulinette.loi_sur_leau_haie.l350_3__loi_sur_leau_haie.result == expected_result
    )


def test_hru_ignores_l350_3_ripisylve():
    """HRU criterion is non_concerne when only L350-3 hedges are ripisylvaires."""
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="alignement", bord_voie=False, ripisylve=False),
            make_hedge(
                hedge_id="D2", type_haie="alignement", bord_voie=True, ripisylve=True
            ),
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.loi_sur_leau_haie.hru__loi_sur_leau_haie.result == "non_concerne"


def test_l350_3_ignores_hru_ripisylve():
    """L350-3 criterion is non_concerne when only HRU hedges are ripisylvaires."""
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="alignement", bord_voie=False, ripisylve=True),
            make_hedge(
                hedge_id="D2", type_haie="alignement", bord_voie=True, ripisylve=False
            ),
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert (
        moulinette.loi_sur_leau_haie.l350_3__loi_sur_leau_haie.result == "non_concerne"
    )


@pytest.mark.parametrize(
    "ripisylve, travaux_berges, technique_consolidation, expected_result",
    [
        # Ripisylve + travaux on a watercourse using non-vegetal technique → soumis
        (True, "cours_eau", "autre", "soumis"),
        # Ripisylve + watercourse but vegetal technique (not "autre") → non_soumis
        (True, "cours_eau", "vegetale", "non_soumis"),
        # Ripisylve + not a watercourse → non_soumis
        (True, "hors_cours_eau", "autre", "non_soumis"),
        # Ripisylve + no consolidation works → non_soumis
        (True, "non", "non", "non_soumis"),
        # No ripisylve → non_concerne regardless of works
        (False, "cours_eau", "autre", "non_concerne"),
    ],
)
def test_ru(ripisylve, travaux_berges, technique_consolidation, expected_result):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(ripisylve=ripisylve, type_haie="mixte")],
        reimplantation="replantation",
        travaux_berges=travaux_berges,
        technique_consolidation=technique_consolidation,
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.loi_sur_leau_haie.ru__loi_sur_leau_haie.result == expected_result


@pytest.mark.parametrize(
    "ripisylve, expected_form_class",
    [
        # A ripisylve hedge is removed → the complementary questions are asked.
        (True, LoiSurLeauHaieRuForm),
        # No ripisylve hedge removed → the two fields are dropped (no form).
        (False, None),
    ],
)
def test_ru_form_is_removed_if_no_ripisylve(ripisylve, expected_form_class):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(ripisylve=ripisylve, type_haie="mixte")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    criterion = moulinette.loi_sur_leau_haie.ru__loi_sur_leau_haie
    assert criterion.get_form_class() is expected_form_class
    if expected_form_class is None:
        # The criterion still resolves without requiring the two fields.
        assert criterion.result == "non_concerne"
