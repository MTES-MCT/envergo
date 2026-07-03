import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
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
    DCConfigHaieFactory()
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
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="alignement", bord_voie=True, ripisylve=True)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.loi_sur_leau_haie.hru__loi_sur_leau_haie.result == "non_concerne"


def test_l350_3_ignores_hru_ripisylve():
    """L350-3 criterion is non_concerne when only HRU hedges are ripisylvaires."""
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[
            make_hedge(type_haie="alignement", bord_voie=False, ripisylve=True)
        ],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert (
        moulinette.loi_sur_leau_haie.l350_3__loi_sur_leau_haie.result == "non_concerne"
    )
