from envergo.moulinette.regulations import CriterionEvaluator

_evaluator_instructors_information_registry = {}


def evaluator_instructors_information_getter(cls):
    """Decorator to register a function that retrieves instructor information for a specific evaluator class."""

    def decorator(func):
        _evaluator_instructors_information_registry[cls] = func
        return func

    return decorator


def get_instructors_information(
    evaluator: CriterionEvaluator, petition_project, moulinette
):
    """
    Retrieve instructor information for a given evaluator using a Class-based Dispatch Registry.

    This function uses a registry pattern to delegate the logic for retrieving
    instructor information to an external function, based on the evaluator's class.
    Each evaluator class must have a corresponding function registered via the
    `@register_instructors_information(SomeEvaluatorClass)` decorator.

    Args:
        evaluator (CriterionEvaluator): An instance of an evaluator class.
        petition_project: The petition project context used in the display logic.
        moulinette: The moulinette instance used to compute evaluation data.

    Returns:
        Any: The result of the registered function associated with the evaluator class.

    Raises:
        NotImplementedError: If no function is registered for the evaluator's class.
    """
    cls = type(evaluator)
    if cls in _evaluator_instructors_information_registry:
        return _evaluator_instructors_information_registry[cls](
            evaluator, petition_project, moulinette
        )
    raise NotImplementedError(f"No info registered for evaluator {cls.__name__}")
