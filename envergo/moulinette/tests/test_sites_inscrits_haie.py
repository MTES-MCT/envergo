import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_EDGE,
    COORDS_BIZOUS_INSIDE,
    COORDS_BIZOUS_OUTSIDE,
    make_hedge,
    make_moulinette_haie_data,
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


MODULE = "envergo.moulinette.regulations.sites_inscrits_haie"

SI_EVALUATORS = (
    f"{MODULE}.SitesInscritsHaieHru",
    f"{MODULE}.SitesInscritsHaieRu",
    f"{MODULE}.SitesInscritsHaieL3503",
)


@pytest.fixture()
def sites_inscrits_criteria(
    sites_inscrits_regulation, sites_inscrits_perimeter, bizous_town_center  # noqa
):
    """One Sites inscrits criterion for each hedge category."""

    criteria = [
        CriterionFactory(
            title="Sites inscrits",
            regulation=sites_inscrits_regulation,
            perimeter=sites_inscrits_perimeter,
            evaluator=evaluator,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )
        for evaluator in SI_EVALUATORS
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
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.sites_inscrits_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.sites_inscrits_haie.hru__si_haie.result == expected_result


@pytest.mark.parametrize(
    "category, hedge_kwargs",
    [
        ("ru", {"type_haie": "mixte"}),
        ("hru", {"type_haie": "alignement", "bord_voie": False}),
        ("l350_3", {"type_haie": "alignement", "bord_voie": True}),
    ],
)
def test_moulinette_evaluation_by_category(
    category, hedge_kwargs, sites_inscrits_criteria
):
    """Under the régime unique, each category gets its own "soumis" result."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, **hedge_kwargs)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.sites_inscrits_haie

    assert regulation.result == "soumis"
    assert getattr(regulation, f"{category}__si_haie").result == "soumis"
