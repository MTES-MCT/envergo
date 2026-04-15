"""Tests for the périmètres de protection de captages regulation."""

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

EVALUATOR_PATHS = (
    "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieRu",
    "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieHru",
    "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieL3503",
)
REGULATION_EVALUATOR_PATH = (
    "envergo.moulinette.regulations.protection_captages" ".ProtectionCaptagesRegulation"
)


@pytest.fixture(autouse=True)
def captage_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(
        regulation="protection_captages",
        evaluator=REGULATION_EVALUATOR_PATH,
        has_perimeters=True,
        show_map=False,
    )
    perimeter = PerimeterFactory(
        name="Captage Bizous",
        activation_map=bizous_town_center,
        regulations=[regulation],
    )
    for evaluator_path in EVALUATOR_PATHS:
        CriterionFactory(
            title="Périmètres de protection de captages",
            regulation=regulation,
            perimeter=perimeter,
            evaluator=evaluator_path,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "a_verifier"),
        (COORDS_BIZOUS_EDGE, "a_verifier"),
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation_without_single_procedure(coords, expected_result):
    """Test that the regulation returns a_verifier when hedges intersect the perimeter."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=coords)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.protection_captages.result == expected_result
    if expected_result != "non_concerne":
        criterion = moulinette.protection_captages.protection_captages__hru
        assert criterion.result == expected_result


@pytest.mark.parametrize(
    "coords, expected_result",
    [
        (COORDS_BIZOUS_INSIDE, "a_verifier"),
        (COORDS_BIZOUS_EDGE, "a_verifier"),
        (COORDS_BIZOUS_OUTSIDE, "non_concerne"),
    ],
)
def test_moulinette_evaluation(coords, expected_result):
    """Test that the regulation returns a_verifier when hedges intersect the perimeter."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="mixte", coords=coords)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.protection_captages.result == expected_result
    if expected_result != "non_concerne":
        criterion = moulinette.protection_captages.protection_captages__ru
        assert criterion.result == expected_result


def test_procedure_type_is_always_declaration():
    """Whatever the result, the procedure type must stay 'declaration'."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="mixte", coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert regulation._evaluator.procedure_type == "declaration"


def test_map_never_displays():
    """The map must never be displayed because the cartographic data is sensitive."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert not regulation.display_map()


def test_map_does_not_display_even_when_non_concerne():
    """The map must not display even when result is non_concerne."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_OUTSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert not regulation.display_map()
