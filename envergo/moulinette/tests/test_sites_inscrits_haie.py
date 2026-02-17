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
    make_haie_data,
    make_hedge,
)


@pytest.fixture()
def sites_inscrits_regulation():
    return RegulationFactory(regulation="sites_inscrits_haie", has_perimeters=True)


@pytest.fixture()
def sites_inscrits_perimeter(sites_inscrits_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="SI Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_inscrits_regulation],
    )


@pytest.fixture()
def sites_inscrits_criteria(
    sites_inscrits_regulation, sites_inscrits_perimeter, bizous_town_center  # noqa
):

    criteria = [
        CriterionFactory(
            title="Sites inscrits",
            regulation=sites_inscrits_regulation,
            perimeter=sites_inscrits_perimeter,
            evaluator="envergo.moulinette.regulations.sites_inscrits_haie.SitesInscritsHaie",
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
def test_moulinette_evaluation(coords, expected_result, sites_inscrits_criteria):
    DCConfigHaieFactory()
    data = make_haie_data(hedge_data=[make_hedge(coords=coords)], reimplantation="replantation")
    moulinette = MoulinetteHaie(data)
    assert moulinette.sites_inscrits_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.sites_inscrits_haie.si_haie.result == expected_result


def test_aa_only_flag(sites_inscrits_criteria):
    """Test that aa_only is True when all hedges are alignement d'arbres."""
    DCConfigHaieFactory(regulations_available=["sites_inscrits_haie"])
    data = make_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, type_haie="alignement")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.catalog.get("aa_only") is True


def test_aa_only_false_with_mixed_hedges(sites_inscrits_criteria):
    """Test that aa_only is False when hedges include non-alignement types."""
    DCConfigHaieFactory(regulations_available=["sites_inscrits_haie"])
    data = make_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.catalog.get("aa_only") is False
