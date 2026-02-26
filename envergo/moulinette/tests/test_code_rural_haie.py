import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import make_moulinette_haie_data, make_hedge


@pytest.fixture(autouse=True)
def code_rural_criteria(request, france_map):  # noqa
    regulation = RegulationFactory(
        regulation="code_rural_haie",
        evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRuralHaieRegulation",
    )

    criteria = [
        CriterionFactory(
            title="Code rural L126-3",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.code_rural_haie.CodeRural",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


def test_moulinette_evaluation():
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(hedge_data=[make_hedge()], reimplantation="replantation")
    moulinette = MoulinetteHaie(data)
    assert moulinette.code_rural_haie.result == "a_verifier"

    assert moulinette.code_rural_haie.code_rural.result == "a_verifier"
