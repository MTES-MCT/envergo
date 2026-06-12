"""Tests for HaieCriterionEvaluator.__init_subclass__ slug/label auto-generation."""

import pytest

from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations.alignementarbres import (
    AlignementsArbresCalvadosBeforeRu,
    AlignementsArbresL3503,
)
from envergo.moulinette.regulations.conditionnalitepac import Bcae8
from envergo.moulinette.regulations.ep import (
    EspecesProtegeesAisne,
    EspecesProtegeesNormandie,
    EspecesProtegeesRegimeUnique,
    EspecesProtegeesSimple,
)
from envergo.moulinette.regulations.protection_captages import (
    ProtectionCaptagesHaieHru,
    ProtectionCaptagesHaieL3503,
    ProtectionCaptagesHaieRu,
)
from envergo.moulinette.regulations.regime_unique_haie import RegimeUniqueHaieRu
from envergo.moulinette.regulations.urbanisme_haie import (
    UrbanismeHaieHru,
    UrbanismeHaieL3503,
    UrbanismeHaieRu,
)


@pytest.mark.parametrize(
    "evaluator_cls, expected_slug",
    [
        (UrbanismeHaieHru, "hru__urbanisme_haie"),
        (UrbanismeHaieRu, "ru__urbanisme_haie"),
        (UrbanismeHaieL3503, "l350_3__urbanisme_haie"),
        (RegimeUniqueHaieRu, "ru__regime_unique_haie"),
        (AlignementsArbresL3503, "l350_3__alignement_arbres"),
        (ProtectionCaptagesHaieHru, "hru__protection_captages"),
        (ProtectionCaptagesHaieRu, "ru__protection_captages"),
        (ProtectionCaptagesHaieL3503, "l350_3__protection_captages"),
    ],
)
def test_slug_auto_generated_from_category_and_base_slug(evaluator_cls, expected_slug):
    assert evaluator_cls.slug == expected_slug


@pytest.mark.parametrize(
    "evaluator_cls, expected_suffix",
    [
        (UrbanismeHaieHru, "Hors régime unique"),
        (UrbanismeHaieRu, "Régime unique"),
        (UrbanismeHaieL3503, "L350-3"),
        (AlignementsArbresL3503, "L350-3"),
        (AlignementsArbresCalvadosBeforeRu, "Hors régime unique"),
    ],
)
def test_choice_label_auto_appends_category_suffix(evaluator_cls, expected_suffix):
    assert evaluator_cls.choice_label.endswith(f" - {expected_suffix}")


@pytest.mark.parametrize(
    "evaluator_cls",
    [EspecesProtegeesSimple, EspecesProtegeesAisne, EspecesProtegeesNormandie, Bcae8],
)
def test_default_category_is_hru(evaluator_cls):
    assert evaluator_cls.category == HedgeCategory.hru
    assert evaluator_cls.slug.startswith("hru__")


def test_explicit_category_override():
    assert EspecesProtegeesRegimeUnique.category == HedgeCategory.ru
    assert EspecesProtegeesRegimeUnique.slug == "ru__ep_regime_unique"


def test_calvados_before_ru_preserves_explicit_slug():
    assert (
        AlignementsArbresCalvadosBeforeRu.slug == "alignement_arbres_calvados_before_ru"
    )
