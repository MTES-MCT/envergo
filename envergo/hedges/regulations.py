from dataclasses import dataclass, field


@dataclass
class PlantationCondition:
    result: bool
    text: str
    context: dict = field(default_factory=dict)


class PlantationConditionMixin:
    """A mixin for a criterion evaluator with hedge replantation conditions.

    This is an "acceptability condition."
    """

    def get_replantation_coefficient(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_replantation_coefficient` method."
        )

    def plantation_evaluate(self, R):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.plantation_evaluate` method."
        )
