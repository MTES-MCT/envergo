from unittest.mock import Mock


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
