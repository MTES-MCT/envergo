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
def sites_classes_regulation():
    return RegulationFactory(regulation="sites_classes_haie", has_perimeters=True)


@pytest.fixture()
def sites_classes_perimeter(sites_classes_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="Site classé de Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_classes_regulation],
    )


MODULE = "envergo.moulinette.regulations.sites_classes_haie"

SITES_CLASSES_EVALUATORS = (
    f"{MODULE}.SitesClassesHaieHru",
    f"{MODULE}.SitesClassesHaieRu",
    f"{MODULE}.SitesClassesHaieL3503",
)


@pytest.fixture()
def sites_classes_criteria(
    sites_classes_regulation, sites_classes_perimeter, bizous_town_center  # noqa
):
    """One Sites classés criterion for each hedge category."""

    return [
        CriterionFactory(
            title="Sites classés",
            regulation=sites_classes_regulation,
            perimeter=sites_classes_perimeter,
            evaluator=evaluator,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )
        for evaluator in SITES_CLASSES_EVALUATORS
    ]


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "soumis"),
        (COORDS_BIZOUS_EDGE, "soumis"),  # edge inside but vertices outside
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation(coords, expected_result, sites_classes_criteria):
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.sites_classes_haie.result == expected_result
    if expected_result != "non_concerne":
        assert (
            moulinette.sites_classes_haie.hru__sites_classes_haie.result
            == expected_result
        )


@pytest.mark.parametrize(
    "category, hedge_kwargs",
    [
        ("ru", {"type_haie": "mixte"}),
        ("hru", {"type_haie": "alignement", "bord_voie": False}),
        ("l350_3", {"type_haie": "alignement", "bord_voie": True}),
    ],
)
def test_moulinette_evaluation_by_category(
    category, hedge_kwargs, sites_classes_criteria
):
    """Under the régime unique, each category gets its own "soumis" result."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, **hedge_kwargs)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.sites_classes_haie

    assert regulation.result == "soumis"
    assert getattr(regulation, f"{category}__sites_classes_haie").result == "soumis"
