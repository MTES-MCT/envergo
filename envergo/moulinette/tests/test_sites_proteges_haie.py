import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_EDGE,
    COORDS_BIZOUS_INSIDE,
    COORDS_BIZOUS_OUTSIDE,
    make_hedge,
    make_moulinette_haie_data,
)


@pytest.fixture()
def sites_proteges_regulation():
    return RegulationFactory(regulation="sites_proteges_haie", has_perimeters=True)


@pytest.fixture()
def mh_perimeter(sites_proteges_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="MH Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )


@pytest.fixture()
def spr_perimeter(sites_proteges_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="SPR Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )


@pytest.fixture()
def sites_proteges_criteria(
    sites_proteges_regulation, spr_perimeter, mh_perimeter, bizous_town_center  # noqa
):

    criteria = [
        CriterionFactory(
            title="Sites Patrimoniaux Remarquables",
            regulation=sites_proteges_regulation,
            perimeter=spr_perimeter,
            evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        ),
        CriterionFactory(
            title="Monuments historiques",
            regulation=sites_proteges_regulation,
            perimeter=mh_perimeter,
            evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        ),
    ]
    return criteria


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "soumis"),
        (COORDS_BIZOUS_EDGE, "soumis"),  # edge inside but vertices outside
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation(coords, expected_result, sites_proteges_criteria):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.sites_proteges_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.sites_proteges_haie.mh_haie.result == expected_result
        assert moulinette.sites_proteges_haie.spr_haie.result == expected_result
