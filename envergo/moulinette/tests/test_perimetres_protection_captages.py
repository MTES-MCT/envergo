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

REGULATION_SLUG = "perimetres_protection_captages"
EVALUATOR_PATH = (
    "envergo.moulinette.regulations.perimetres_protection_captages"
    ".PerimetresProtectionCaptagesHaie"
)
REGULATION_EVALUATOR_PATH = (
    "envergo.moulinette.regulations.perimetres_protection_captages"
    ".PerimetresProtectionCaptagesRegulation"
)


@pytest.fixture()
def captage_regulation():
    return RegulationFactory(
        regulation=REGULATION_SLUG,
        evaluator=REGULATION_EVALUATOR_PATH,
        has_perimeters=True,
        show_map=False,
    )


@pytest.fixture()
def captage_perimeter(captage_regulation, bizous_town_center):
    return PerimeterFactory(
        name="Captage Bizous",
        activation_map=bizous_town_center,
        regulations=[captage_regulation],
    )


@pytest.fixture()
def captage_criteria(captage_regulation, captage_perimeter, bizous_town_center):
    criteria = [
        CriterionFactory(
            title="Périmètres de protection de captages",
            regulation=captage_regulation,
            perimeter=captage_perimeter,
            evaluator=EVALUATOR_PATH,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        ),
    ]
    return criteria


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "a_verifier"),
        (COORDS_BIZOUS_EDGE, "a_verifier"),
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation(coords, expected_result, captage_criteria):
    """Test that the regulation returns a_verifier when hedges intersect the perimeter."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.perimetres_protection_captages.result == expected_result
    if expected_result != "non_concerne":
        criterion = moulinette.perimetres_protection_captages.perimetres_protection_captages
        assert criterion.result == expected_result


def test_procedure_type_is_always_declaration(captage_criteria):
    """Whatever the result, the procedure type must stay 'declaration'."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.perimetres_protection_captages
    assert regulation._evaluator.procedure_type == "declaration"


def test_map_never_displays(captage_criteria):
    """The map must never be displayed because the cartographic data is sensitive."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.perimetres_protection_captages
    assert not regulation.display_map()


def test_map_does_not_display_even_when_non_concerne(captage_criteria):
    """The map must not display even when result is non_concerne."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_OUTSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.perimetres_protection_captages
    assert not regulation.display_map()
