from envergo.moulinette.regulations import CriterionEvaluator, RegulationEvaluator

_evaluator_instructors_information_registry = {}


def evaluator_instructor_view_context_getter(cls):
    """Register a function that builds instructor-view context for an evaluator class.

    The decorated function must accept four positional arguments:
    ``(evaluator, petition_project, moulinette, plantation_evaluation)``.
    ``plantation_evaluation`` may be ``None`` when no plantation data is
    available (e.g. in tests or non-plantation views).
    """

    def decorator(func):
        _evaluator_instructors_information_registry[cls] = func
        return func

    return decorator


def get_instructor_view_context(
    evaluator: CriterionEvaluator | RegulationEvaluator,
    petition_project,
    moulinette,
    plantation_evaluation=None,
):
    """Retrieve instructor view context for a given evaluator.

    Uses a class-based dispatch registry: each evaluator class can register
    a context-building function via ``@evaluator_instructor_view_context_getter``.

    ``plantation_evaluation`` is an already-evaluated ``PlantationEvaluator``
    that registry functions can query for pre-computed plantation conditions
    instead of re-evaluating them.
    """
    cls = type(evaluator)
    if cls in _evaluator_instructors_information_registry:
        return _evaluator_instructors_information_registry[cls](
            evaluator, petition_project, moulinette, plantation_evaluation
        )
    return {}
