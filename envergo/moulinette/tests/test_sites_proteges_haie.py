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


MODULE = "envergo.moulinette.regulations.sites_proteges_haie"

SPR_EVALUATORS = (
    f"{MODULE}.SitesPatrimoniauxRemarquablesHaieHru",
    f"{MODULE}.SitesPatrimoniauxRemarquablesHaieRu",
    f"{MODULE}.SitesPatrimoniauxRemarquablesHaieL3503",
)

MH_EVALUATORS = (
    f"{MODULE}.MonumentsHistoriquesHaieHru",
    f"{MODULE}.MonumentsHistoriquesHaieRu",
    f"{MODULE}.MonumentsHistoriquesHaieL3503",
)


@pytest.fixture()
def sites_proteges_criteria(
    sites_proteges_regulation, spr_perimeter, mh_perimeter, bizous_town_center  # noqa
):
    """One SPR and one MH criterion for each hedge category."""

    criteria = [
        CriterionFactory(
            title="Sites Patrimoniaux Remarquables",
            regulation=sites_proteges_regulation,
            perimeter=spr_perimeter,
            evaluator=evaluator,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )
        for evaluator in SPR_EVALUATORS
    ] + [
        CriterionFactory(
            title="Monuments historiques",
            regulation=sites_proteges_regulation,
            perimeter=mh_perimeter,
            evaluator=evaluator,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )
        for evaluator in MH_EVALUATORS
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
        assert moulinette.sites_proteges_haie.hru__mh_haie.result == expected_result
        assert moulinette.sites_proteges_haie.hru__spr_haie.result == expected_result


@pytest.mark.parametrize(
    "category, hedge_kwargs",
    [
        ("ru", {"type_haie": "mixte"}),
        ("hru", {"type_haie": "alignement", "bord_voie": False}),
        ("l350_3", {"type_haie": "alignement", "bord_voie": True}),
    ],
)
def test_moulinette_evaluation_by_category(
    category, hedge_kwargs, sites_proteges_criteria
):
    """Under the régime unique, each category gets its own "soumis" result."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, **hedge_kwargs)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.sites_proteges_haie

    assert regulation.result == "soumis"
    assert getattr(regulation, f"{category}__spr_haie").result == "soumis"
    assert getattr(regulation, f"{category}__mh_haie").result == "soumis"
