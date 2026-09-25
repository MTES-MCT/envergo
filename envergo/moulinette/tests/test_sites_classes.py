import pytest
from django.template import Context

from envergo.hedges.models import HedgeCategory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.templatetags.moulinette import show_regulation_body
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
def sites_classes_regulation():
    return RegulationFactory(
        regulation="sites_classes_haie",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.sites_classes_haie.SitesClassesRegulation",
    )


@pytest.fixture()
def sites_classes_perimeter(sites_classes_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="Site classé de Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_classes_regulation],
    )


@pytest.fixture()
def sites_classes_criterion(
    sites_classes_regulation, sites_classes_perimeter, bizous_town_center  # noqa
):
    return CriterionFactory(
        title="Sites classés",
        regulation=sites_classes_regulation,
        perimeter=sites_classes_perimeter,
        evaluator="envergo.moulinette.regulations.sites_classes_haie.SitesClassesHaie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "soumis"),
        (COORDS_BIZOUS_EDGE, "soumis"),  # edge inside but vertices outside
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation(coords, expected_result, sites_classes_criterion):
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


def aa_only(moulinette):
    """The flag computed by the sites classés regulation for the hru hedges."""
    evaluator = moulinette.sites_classes_haie.get_evaluator()
    return evaluator.aa_only_by_category[HedgeCategory.hru]


def test_aa_only_flag(sites_classes_criterion):
    """Test that aa_only is True when all hedges are alignement d'arbres."""
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, type_haie="alignement")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert aa_only(moulinette) is True


def test_aa_only_false_with_mixed_hedges(sites_classes_criterion):
    """Test that aa_only is False when hedges include non-alignement types."""
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert aa_only(moulinette) is False


def test_regulation_body_reads_the_flag_of_its_category(sites_classes_criterion):
    """The regulation template reads the flag from the regulation evaluator."""
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE, type_haie="alignement")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    context = Context(
        {
            "moulinette": moulinette,
            "config": moulinette.config,
            "category": HedgeCategory.hru,
        }
    )
    body = show_regulation_body(
        context, moulinette.sites_classes_haie, HedgeCategory.hru
    )
    assert "soumis à autorisation spéciale" in body
