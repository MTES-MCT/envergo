import pytest

from envergo.hedges.models import HedgeTypeBase
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


@pytest.fixture
def n2000_criteria(bizous_town_center):
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
def test_moulinette_evaluation(coords, expected_result, n2000_criteria):
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
def test_moulinette_evaluation_alignement(coords, expected_result, n2000_criteria):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords, type_haie="alignement")],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.natura2000_haie.natura2000_haie.result_code == expected_result


class TestConcerneAAParam:
    """Test the concerne_aa parameter across all combinations of settings and hedge types."""

    # fmt: off
    @pytest.mark.parametrize(
        "concerne_aa, result, hedge_types, expected_result_code",
        [
            # concerne_aa=True, result=soumis
            (True, "soumis", [HedgeTypeBase.ALIGNEMENT], "soumis"),
            (True, "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "soumis"),
            (True, "soumis", [HedgeTypeBase.BUISSONNANTE], "soumis"),
            # concerne_aa=True, result=non_soumis
            (True, "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            (True, "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            (True, "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_soumis"),
            # concerne_aa=False, result=soumis
            (False, "soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis_aa"),
            (False, "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "soumis"),
            (False, "soumis", [HedgeTypeBase.BUISSONNANTE], "soumis"),
            # concerne_aa=False, result=non_soumis
            (False, "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis_aa"),
            (False, "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            (False, "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_soumis"),
            # result non renseigné, concerne_aa renseigné → settings form invalide → non_disponible
            (True, None, [HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (True, None, [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (True, None, [HedgeTypeBase.BUISSONNANTE], "non_disponible"),
            # concerne_aa non renseigné, result renseigné → concerne_aa=False par défaut
            (None, "soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis_aa"),
            (None, "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "soumis"),
            (None, "soumis", [HedgeTypeBase.BUISSONNANTE], "soumis"),
            (None, "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis_aa"),
            (None, "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            (None, "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_soumis"),
            # ni concerne_aa ni result renseignés → settings form invalide → non_disponible
            (None, None, [HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, None, [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, None, [HedgeTypeBase.BUISSONNANTE], "non_disponible"),
        ],
    )
    # fmt: on
    def test_result_code(
        self,
        concerne_aa,
        result,
        hedge_types,
        expected_result_code,
        bizous_town_center,
    ):
        regulation = RegulationFactory(
            regulation="natura2000_haie", has_perimeters=True
        )
        perimeter = PerimeterFactory(
            name="N2000 Bizous",
            activation_map=bizous_town_center,
            regulations=[regulation],
        )
        evaluator_settings = {}
        if result is not None:
            evaluator_settings["result"] = result
        if concerne_aa:
            evaluator_settings["concerne_aa"] = True
        CriterionFactory(
            title="Natura 2000 Haie > Test",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            evaluator_settings=evaluator_settings,
        )
        DCConfigHaieFactory()
        hedge_data = [
            make_hedge(
                coords=COORDS_BIZOUS_INSIDE,
                type_haie=ht,
                hedge_id=f"D{i}",
            )
            for i, ht in enumerate(hedge_types)
        ]
        data = make_moulinette_haie_data(
            hedge_data=hedge_data,
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        assert (
            moulinette.natura2000_haie.natura2000_haie.result_code
            == expected_result_code
        )  # noqa: E501
