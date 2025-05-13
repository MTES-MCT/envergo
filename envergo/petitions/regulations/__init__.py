from envergo.moulinette.regulations import CriterionEvaluator

_evaluator_instructors_information_registry = {}


def register_instructors_information(cls):
    def decorator(func):
        _evaluator_instructors_information_registry[cls] = func
        return func

    return decorator


def get_instructors_information(
    evaluator: CriterionEvaluator, petition_project, moulinette
):
    cls = type(evaluator)
    if cls in _evaluator_instructors_information_registry:
        return _evaluator_instructors_information_registry[cls](
            evaluator, petition_project, moulinette
        )
    raise NotImplementedError(f"No info registered for evaluator {cls.__name__}")
