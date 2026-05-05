import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data


@pytest.fixture(autouse=True)
def regime_unique_haie_criteria(request, france_map):  # noqa
    regulation = RegulationFactory(
        regulation="regime_unique_haie",
        evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRegulation",
    )
    if request.node.get_closest_marker("disable_regime_haie_criterion"):
        return

    criteria = [
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieHru",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRu",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieL3503",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.mark.parametrize(
    "type_haie, expected_result, expected_result_code",
    [
        (
            "mixte",
            "soumis",
            "soumis",
        ),
        (
            "alignement",
            "non_concerne",
            "non_concerne",
        ),
    ],
)
def test_moulinette_evaluation_single_procedure(
    type_haie, expected_result, expected_result_code
):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
    if type_haie == "mixte":
        criterion = moulinette.regime_unique_haie.ru__regime_unique_haie
    else:
        criterion = moulinette.regime_unique_haie.l350_3__regime_unique_haie

    assert criterion.result_code == expected_result_code


@pytest.mark.parametrize(
    "type_haie, expected_result, expected_result_code",
    [
        ("mixte", "non_active", "non_active"),
        ("alignement", "non_active", "non_active"),
    ],
)
def test_moulinette_evaluation_droit_constant(
    type_haie, expected_result, expected_result_code
):
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert (
        moulinette.regime_unique_haie.hru__regime_unique_haie.result_code
        == expected_result_code
    )


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_active"), ("alignement", "non_active")],
)
def test_moulinette_evaluation_non_active(type_haie, expected_result):
    RUConfigHaieFactory(regulations_available=[])
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_disponible"), ("alignement", "non_disponible")],
)
@pytest.mark.disable_regime_haie_criterion
def test_moulinette_evaluation_non_disponible(type_haie, expected_result):
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie=type_haie)], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.regime_unique_haie.result == expected_result
