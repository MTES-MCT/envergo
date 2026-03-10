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


@pytest.fixture(autouse=True)
def n2000_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(regulation="natura2000_haie", has_perimeters=True)

    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            evaluator_settings={"result": "soumis"},
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
def test_moulinette_evaluation(coords, expected_result):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.natura2000_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.natura2000_haie.natura2000_haie.result == expected_result


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "non_soumis_aa"),
        (COORDS_BIZOUS_EDGE, "non_soumis_aa"),  # edge inside but vertices outside
    ],
)
def test_moulinette_evaluation_alignement(coords, expected_result):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords, type_haie="alignement")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.natura2000_haie.natura2000_haie.result_code == expected_result
