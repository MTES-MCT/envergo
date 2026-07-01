from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa: F401
from envergo.moulinette.tests.utils import (
    setup_ep_regime_unique,
    setup_regime_unique_haie,
)


def make_mock_evaluator(
    single_procedure=False,
    result_code="soumis",
    effective_coefficients=None,
):
    """Create a mock criterion evaluator."""
    ev = Mock()
    ev.moulinette.config.single_procedure = single_procedure
    ev.result_code = result_code
    ev.effective_coefficients = (
        effective_coefficients if effective_coefficients is not None else {}
    )
    return ev


@pytest.fixture
def ep_ru_criterion(france_map):  # noqa: F811
    """Create an EP regulation with a single EspecesProtegeesRegimeUnique criterion."""
    _regulation, criteria = setup_ep_regime_unique(france_map)
    return criteria


@pytest.fixture
def ru_criterion(france_map):  # noqa: F811
    """Create a Régime unique haie regulation with its criterion."""
    _regulation, criteria = setup_regime_unique_haie(france_map)
    return criteria
