"""Shared mock factories for hedge condition tests."""

from itertools import count
from unittest.mock import Mock

_hedge_counter = count(1)


def make_mock_hedge(hedge_type, length, hedge_id=None):
    """Create a mock hedge with type, length, and a unique id."""
    h = Mock()
    h.hedge_type = hedge_type
    h.length = length
    h.id = hedge_id or f"mock_{next(_hedge_counter)}"
    return h


def make_mock_hedge_data(to_remove, to_plant):
    """Create a mock HedgeData with the given hedges to remove and plant."""
    hd = Mock()
    hd.hedges_to_remove.return_value = to_remove
    hd.hedges_to_plant.return_value = to_plant
    return hd


def make_mock_evaluator(single_procedure=False, result_code="soumis", ep_bonus=None):
    """Create a mock criterion evaluator.

    Set ``ep_bonus`` to wire up ``get_ep_ru_bonus`` (needed for RU tests).
    """
    ev = Mock()
    ev.moulinette.config.single_procedure = single_procedure
    ev.result_code = result_code
    if ep_bonus is not None:
        ev.get_ep_ru_bonus.return_value = ep_bonus
    return ev
