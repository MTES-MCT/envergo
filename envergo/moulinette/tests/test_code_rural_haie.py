import pytest

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data

EVALUATOR_PATHS = (
    "envergo.moulinette.regulations.code_rural_haie.CodeRuralHru",
    "envergo.moulinette.regulations.code_rural_haie.CodeRuralRu",
    "envergo.moulinette.regulations.code_rural_haie.CodeRuralL3503",
)


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
            evaluator=evaluator_path,
            activation_map=france_map,
            activation_mode="department_centroid",
        )
        for evaluator_path in EVALUATOR_PATHS
    ]
    return criteria


def test_moulinette_evaluation():
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge()], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    assert moulinette.code_rural_haie.result == "a_verifier"

    assert moulinette.code_rural_haie.hru__code_rural.result == "a_verifier"


def test_moulinette_evaluation_ru_category():
    """A hedge covered by the régime unique always yields "a_verifier"."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="mixte")], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.code_rural_haie

    assert regulation.result == "a_verifier"
    assert regulation.ru__code_rural.result == "a_verifier"


def test_moulinette_evaluation_hru_category():
    """A hedge outside the régime unique always yields "a_verifier"."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="alignement", bord_voie=False)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.code_rural_haie

    assert regulation.result == "a_verifier"
    assert regulation.hru__code_rural.result == "a_verifier"


def test_moulinette_evaluation_l350_3_category():
    """A roadside tree alignment always yields "a_verifier"."""

    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="alignement", bord_voie=True)],
        reimplantation="replantation",
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.code_rural_haie

    assert regulation.result == "a_verifier"
    assert regulation.l350_3__code_rural.result == "a_verifier"


def test_procedure_type_is_always_declaration():
    RUConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(type_haie="mixte")], reimplantation="replantation"
    )
    moulinette = MoulinetteHaie(data)
    regulation = moulinette.code_rural_haie
    assert regulation._evaluator.procedure_type == "declaration"
