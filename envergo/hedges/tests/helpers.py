"""Shared test factories for hedge condition tests."""

from unittest.mock import Mock

from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory


def make_hedge_to_remove(hedge_type, length, hedge_id=None):
    """Create a hedge-to-remove with the given type and approximate length."""
    kwargs = {"additionalData": {"type_haie": hedge_type}, "length": length}
    if hedge_id is not None:
        kwargs["id"] = hedge_id
    return HedgeFactory(**kwargs)


def make_hedge_to_plant(hedge_type, length, hedge_id=None):
    """Create a hedge-to-plant with the given type and approximate length."""
    kwargs = {
        "type": "TO_PLANT",
        "additionalData": {"type_haie": hedge_type},
        "length": length,
    }
    if hedge_id is not None:
        kwargs["id"] = hedge_id
    return HedgeFactory(**kwargs)


def make_hedge_data(to_remove=None, to_plant=None):
    """Create a HedgeData from lists of hedges to remove and plant."""
    hedges = list(to_remove or []) + list(to_plant or [])
    return HedgeDataFactory(hedges=hedges)


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
