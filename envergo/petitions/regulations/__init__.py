from envergo.moulinette.regulations import CriterionEvaluator, RegulationEvaluator

_evaluator_instructors_information_registry = {}


def evaluator_instructor_view_context_getter(cls):
    """Decorator to register a function that retrieves instructor information for a specific evaluator class."""

    def decorator(func):
        _evaluator_instructors_information_registry[cls] = func
        return func

    return decorator


def get_instructor_view_context(
    evaluator: CriterionEvaluator | RegulationEvaluator, petition_project, moulinette
):
    """
    Retrieve instructor information for a given evaluator using a Class-based Dispatch Registry.

    This function uses a registry pattern to delegate the logic for retrieving
    instructor information to an external function, based on the evaluator's class.
    Each evaluator class can have a corresponding function registered via the
    `@register_instructors_information(SomeEvaluatorClass)` decorator.

    It allows for cleaner code organization and separation of concerns, as the
    logic for each evaluator's instructor information can be defined in a dedicated App,
     rather than being mixed into a single large function.

    Args:
        evaluator (CriterionEvaluator): An instance of an evaluator class.
        petition_project: The petition project context used in the display logic.
        moulinette: The moulinette instance used to compute evaluation data.

    Returns:
        tuple[str, dict]: A couple template/context to display evaluator's instructors info.

    Raises:
        NotImplementedError: If no function is registered for the evaluator's class.
    """
    cls = type(evaluator)
    if cls in _evaluator_instructors_information_registry:
        return _evaluator_instructors_information_registry[cls](
            evaluator, petition_project, moulinette
        )
    # if there is no specific function registered for this evaluator class, return an empty context
    return {}
