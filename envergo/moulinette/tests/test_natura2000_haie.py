import pytest

from envergo.hedges.models import HedgeTypeBase
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.regulations.natura2000_haie import (
    Natura2000HaieRuSettings,
    Natura2000HaieSettings,
)
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

HRU = "envergo.moulinette.regulations.natura2000_haie.Natura2000HaieHru"
RU = "envergo.moulinette.regulations.natura2000_haie.Natura2000HaieRu"
L350_3 = "envergo.moulinette.regulations.natura2000_haie.Natura2000HaieL3503"


def make_n2000_criteria(activation_map, settings_by_evaluator):
    """Create one N2000 criterion per evaluator, all on the same activation map."""

    regulation = RegulationFactory(
        regulation="natura2000_haie",
        evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000HaieRegulation",
        has_perimeters=True,
    )
    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=activation_map, regulations=[regulation]
    )
    return [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator=evaluator,
            activation_map=activation_map,
            activation_mode="hedges_intersection",
            evaluator_settings=settings,
        )
        for evaluator, settings in settings_by_evaluator.items()
    ]


@pytest.fixture
def n2000_criteria(bizous_town_center):
    return make_n2000_criteria(
        bizous_town_center,
        {
            HRU: {"result": "soumis", "concerne_aa": "non"},
            L350_3: {"result": "soumis", "concerne_aa": "non"},
            RU: {"result": "soumis"},
        },
    )


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
        assert moulinette.natura2000_haie.hru__natura2000_haie.result == expected_result


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
    assert (
        moulinette.natura2000_haie.hru__natura2000_haie.result_code == expected_result
    )


class TestCategories:
    """Each hedge category is evaluated by its own criterion."""

    @pytest.mark.parametrize(
        "hedge, slug",
        [
            # A mixed hedge falls under the régime unique…
            ({"type_haie": "mixte"}, "ru__natura2000_haie"),
            # …a roadside tree alignment under L350-3…
            ({"type_haie": "alignement", "bord_voie": True}, "l350_3__natura2000_haie"),
            # …and any other tree alignment stays outside the régime unique.
            ({"type_haie": "alignement", "bord_voie": False}, "hru__natura2000_haie"),
        ],
    )
    def test_the_matching_criterion_is_evaluated(self, hedge, slug, n2000_criteria):
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(**hedge)], reimplantation="replantation"
        )
        moulinette = MoulinetteHaie(data)
        regulation = moulinette.natura2000_haie

        assert getattr(regulation, slug).result_code in ("soumis", "non_soumis_aa")

    @pytest.mark.parametrize("result", ["soumis", "non_soumis"])
    def test_ru_result_comes_from_the_settings(self, result, bizous_town_center):
        """The régime unique result only depends on the `result` setting."""

        make_n2000_criteria(bizous_town_center, {RU: {"result": result}})
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")], reimplantation="replantation"
        )
        moulinette = MoulinetteHaie(data)

        assert moulinette.natura2000_haie.ru__natura2000_haie.result_code == result
        assert moulinette.natura2000_haie.results_by_category["ru"] == result

    def test_ru_is_non_concerne_without_hedge_to_remove_in_the_map(
        self, bizous_town_center
    ):
        """Only hedges to plant inside the site: nothing is destroyed there."""

        make_n2000_criteria(bizous_town_center, {RU: {"result": "soumis"}})
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[
                make_hedge(
                    hedge_id="D1", coords=COORDS_BIZOUS_OUTSIDE, type_haie="mixte"
                ),
                make_hedge(
                    hedge_id="P1",
                    hedge_type="TO_PLANT",
                    coords=COORDS_BIZOUS_INSIDE,
                    type_haie="mixte",
                ),
            ],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)

        assert (
            moulinette.natura2000_haie.ru__natura2000_haie.result_code == "non_concerne"
        )

    def test_l350_3_is_evaluated_like_hru(self, bizous_town_center):
        """L350-3 keeps the `concerne_aa` setting: alignments are excluded."""

        make_n2000_criteria(
            bizous_town_center, {L350_3: {"result": "soumis", "concerne_aa": "non"}}
        )
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="alignement", bord_voie=True)],
            reimplantation="replantation",
        )
        moulinette = MoulinetteHaie(data)
        criterion = moulinette.natura2000_haie.l350_3__natura2000_haie

        assert criterion.result_code == "non_soumis_aa"
        assert criterion.result == "non_soumis"


class TestNatura2000HaieSettings:
    """Test the Natura2000HaieSettings form validation."""

    def test_concerne_aa_accepts_oui(self):
        form = Natura2000HaieSettings({"result": "soumis", "concerne_aa": "oui"})
        assert form.is_valid()

    def test_concerne_aa_accepts_non(self):
        form = Natura2000HaieSettings({"result": "soumis", "concerne_aa": "non"})
        assert form.is_valid()

    def test_ru_settings_do_not_require_concerne_aa(self):
        form = Natura2000HaieRuSettings({"result": "soumis"})
        assert form.is_valid()
        assert "concerne_aa" not in form.fields

    def test_ru_settings_require_a_result(self):
        form = Natura2000HaieRuSettings({})
        assert not form.is_valid()


class TestConcerneAAParam:
    """Test the concerne_aa parameter across all combinations of settings and hedge types."""

    # fmt: off
    @pytest.mark.parametrize(
        "concerne_aa, result, hedge_types, expected_result_code",
        [
            # concerne_aa="oui", result=soumis
            ("oui", "soumis", [HedgeTypeBase.ALIGNEMENT], "soumis"),
            ("oui", "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "soumis"),
            ("oui", "soumis", [HedgeTypeBase.BUISSONNANTE], "soumis"),
            # concerne_aa="oui", result=non_soumis
            ("oui", "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            ("oui", "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            ("oui", "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_soumis"),
            # concerne_aa="non", result=soumis
            ("non", "soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis_aa"),
            ("non", "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "soumis"),
            ("non", "soumis", [HedgeTypeBase.BUISSONNANTE], "soumis"),
            # concerne_aa="non", result=non_soumis
            ("non", "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            ("non", "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_soumis"),
            ("non", "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_soumis"),
            # result non renseigné, concerne_aa renseigné → settings form invalide → non_disponible
            ("oui", None, [HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            ("oui", None, [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            ("oui", None, [HedgeTypeBase.BUISSONNANTE], "non_disponible"),
            # concerne_aa non renseigné, result renseigné → settings form invalide → non_disponible
            (None, "soumis", [HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, "soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, "soumis", [HedgeTypeBase.BUISSONNANTE], "non_disponible"),
            (None, "non_soumis", [HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, "non_soumis", [HedgeTypeBase.BUISSONNANTE, HedgeTypeBase.ALIGNEMENT], "non_disponible"),
            (None, "non_soumis", [HedgeTypeBase.BUISSONNANTE], "non_disponible"),
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
        evaluator_settings = {}
        if result is not None:
            evaluator_settings["result"] = result
        if concerne_aa is not None:
            evaluator_settings["concerne_aa"] = concerne_aa
        make_n2000_criteria(bizous_town_center, {HRU: evaluator_settings})
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
            moulinette.natura2000_haie.hru__natura2000_haie.result_code
            == expected_result_code
        )  # noqa: E501
