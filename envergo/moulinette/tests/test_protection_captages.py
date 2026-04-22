"""Tests for the périmètres de protection de captages regulation."""

from urllib.parse import urlencode

import pytest
from django.urls import reverse

from envergo.hedges.tests.factories import HedgeDataFactory
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
    "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesRegulation"
)


@pytest.fixture
def captage_criteria(bizous_town_center):
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
def test_moulinette_evaluation_without_single_procedure(
    captage_criteria, coords, expected_result
):
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
def test_moulinette_evaluation(captage_criteria, coords, expected_result):
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


def test_procedure_type_is_always_declaration(captage_criteria):
    """Whatever the result, the procedure type must stay 'declaration'."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="mixte", coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert regulation._evaluator.procedure_type == "declaration"


def test_map_never_displays(captage_criteria):
    """The map must never be displayed because the cartographic data is sensitive."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert not regulation.display_map()


def test_map_does_not_display_even_when_non_concerne(captage_criteria):
    """The map must not display even when result is non_concerne."""

    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_OUTSIDE)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.protection_captages
    assert not regulation.display_map()


@pytest.mark.haie
def test_perimeter_detail_hidden_when_map_not_displayed(bizous_town_center, client):
    """When show_map is False, the perimeter detail must not appear in the HTML."""
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

    DCConfigHaieFactory()
    hedges = HedgeDataFactory(data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "contexte": "non",
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "department": "44",
        "haies": hedges.id,
    }
    url = reverse("moulinette_result")
    res = client.get(f"{url}?{urlencode(data)}")

    assert res.status_code == 200
    assert "Le projet se trouve dans le périmètre" not in res.content.decode()


@pytest.mark.haie
def test_perimeter_detail_shown_when_map_displayed(bizous_town_center, client):
    """When show_map is True, the perimeter detail must appear in the HTML."""
    regulation = RegulationFactory(
        regulation="protection_captages",
        evaluator=REGULATION_EVALUATOR_PATH,
        has_perimeters=True,
        show_map=True,
        map_factory_name="envergo.moulinette.regulations.PerimetersBoundedWithCenterMapMarkerMapFactory",
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

    DCConfigHaieFactory()
    hedges = HedgeDataFactory(data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)])
    data = {
        "element": "haie",
        "travaux": "destruction",
        "contexte": "non",
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "department": "44",
        "haies": hedges.id,
    }
    url = reverse("moulinette_result")
    res = client.get(f"{url}?{urlencode(data)}")

    assert res.status_code == 200
    assert "Le projet se trouve dans le périmètre" in res.content.decode()
