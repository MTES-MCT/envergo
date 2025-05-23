from dataclasses import dataclass
from decimal import Decimal as D
from enum import Enum
from itertools import product
from operator import attrgetter
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal

from django.contrib.gis.geos import GEOSGeometry, MultiLineString

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Line
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.regulations import MinLengthCondition
from envergo.moulinette.models import GLOBAL_RESULT_MATRIX
from envergo.moulinette.regulations import Map, MapPolygon

if TYPE_CHECKING:
    from envergo.hedges.models import HedgeData
    from envergo.moulinette.models import MoulinetteHaie


class PlantationResults(Enum):
    Adequate = "adequate"
    Inadequate = "inadequate"


PLANTATION_RESULT_MATRIX = {
    (RESULTS.interdit, PlantationResults.Inadequate.value): RESULTS.interdit,
    (RESULTS.interdit, PlantationResults.Adequate.value): RESULTS.interdit,
    (
        RESULTS.soumis,
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    (RESULTS.soumis, PlantationResults.Adequate.value): RESULTS.soumis,
    (RESULTS.non_soumis, PlantationResults.Adequate.value): RESULTS.non_soumis,
    (
        RESULTS.non_soumis,
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    # not used for now:
    (
        RESULTS.action_requise,
        PlantationResults.Inadequate.value,
    ): RESULTS.non_disponible,
    (RESULTS.action_requise, PlantationResults.Adequate.value): RESULTS.non_disponible,
    (
        RESULTS.non_disponible,
        PlantationResults.Inadequate.value,
    ): RESULTS.non_disponible,
    (RESULTS.non_disponible, PlantationResults.Adequate.value): RESULTS.non_disponible,
}


def _check_plantation_result_matrix():
    all_global_results = [
        global_result for global_result in set(GLOBAL_RESULT_MATRIX.values())
    ]
    all_plantation_results = [p.value for p in PlantationResults]

    # Generate all possible combinations
    expected_combinations = set(product(all_global_results, all_plantation_results))

    # Get actual keys from the matrix
    existing_combinations = set(PLANTATION_RESULT_MATRIX.keys())

    # Find missing combinations
    missing_combinations = expected_combinations - existing_combinations

    # Raise an error if there are missing cases
    if missing_combinations:
        raise ValueError(
            f"Missing cases in PLANTATION_RESULT_MATRIX: {missing_combinations}"
        )


_check_plantation_result_matrix()


# This method is outside the PlantationEvaluator class because it makes it
# easier to patch it in tests.
def get_replantation_coefficient(moulinette):
    """Get the "R" value.

    It depends on the activated criteria.
    """
    R = D("0")
    for regulation in moulinette.regulations:
        if regulation.is_activated():
            for criterion in regulation.criteria.all():
                if hasattr(criterion._evaluator, "get_replantation_coefficient"):
                    R = max(R, criterion._evaluator.get_replantation_coefficient())

    return float(R)


def create_density_map(
    centroid_geos, hedges_to_remove, truncated_circle_200, truncated_circle_5000
):
    hedges_5000 = (
        Line.objects.filter(
            map__map_type=MAP_TYPES.haies,
            geometry__intersects=truncated_circle_5000,
        )
        if truncated_circle_5000
        else []
    )

    polygons = [
        MapPolygon(
            [SimpleNamespace(geometry=truncated_circle_200)],
            "orange",
            "200m",
        ),
        MapPolygon(
            [SimpleNamespace(geometry=truncated_circle_5000)],
            "blue",
            "5km",
        ),
        MapPolygon(
            [
                SimpleNamespace(
                    geometry=MultiLineString(
                        [hedge.geometry for hedge in hedges_5000],
                        srid=EPSG_WGS84,
                    )
                )
            ],
            "green",
            "Haies existantes",
        ),
        MapPolygon(
            [
                SimpleNamespace(
                    geometry=GEOSGeometry(hedge.geometry.wkt, srid=EPSG_WGS84)
                )
                for hedge in hedges_to_remove
            ],
            "red",
            "Haies à détruire",
            class_name="hedge to-remove",
        ),
    ]

    return Map(
        type="regulation",
        center=centroid_geos,
        entries=polygons,
        truncate=False,
        display_marker_at_center=True,
        zoom=None,
        ratio_classes="ratio-2x1 ratio-sm-4x5",
        fixed=False,
    )


@dataclass
class EvaluationResult:
    result: Literal[PlantationResults.Adequate, PlantationResults.Inadequate]
    conditions: list[str]
    evaluation: dict


class PlantationEvaluator:
    """Evaluate the adequacy of a plantation project.

    The plantation evaluator is used to evaluate if a project is compliant with the regulation.
    """

    def __init__(self, moulinette: "MoulinetteHaie", hedge_data: "HedgeData"):
        self.moulinette = moulinette
        self.hedge_data = hedge_data
        self.replantation_coefficient = get_replantation_coefficient(moulinette)

    @property
    def result(self):
        """Return the evaluator result.

        This value is used to select the plantation result templates.
        """
        if not hasattr(self, "_result"):
            self.evaluate()

        return self._result

    @property
    def conditions(self):
        if not hasattr(self, "_conditions"):
            self.evaluate()

        return self._conditions

    @property
    def global_result(self):
        """Return the project result combining both removal and plantation.

        This value is used to select the plantation result templates.
        """
        return PLANTATION_RESULT_MATRIX.get(
            (self.moulinette.result, self.result), RESULTS.interdit
        )

    @property
    def result_code(self):
        """Return the plantation evaluator result code.

        The result code is a unique code used to render the criterion template.
        """
        return f"{self.moulinette.result}_{self.result}"

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""

        R = self.replantation_coefficient
        conditions = [MinLengthCondition(self.hedge_data, R).evaluate()]
        for regulation in self.moulinette.regulations:
            for criterion in regulation.criteria.all():
                if hasattr(criterion._evaluator, "plantation_evaluate"):
                    conditions.extend(
                        criterion._evaluator.plantation_evaluate(self.hedge_data, R)
                    )

        self._conditions = sorted(conditions, key=attrgetter("order"))
        self._result = (
            PlantationResults.Adequate.value
            if len(self.invalid_conditions) == 0
            else PlantationResults.Inadequate.value
        )

    def get_context(self):
        context = {}
        for condition in self.conditions:
            context.update(condition.context)
        return context

    @property
    def valid_conditions(self):
        return [condition for condition in self.conditions if condition.result]

    @property
    def invalid_conditions(self):
        return [condition for condition in self.conditions if not condition.result]

    def to_json(self):
        data = [
            {
                "label": condition.label,
                "result": condition.result,
                "text": condition.text,
                "context": condition.context,
            }
            for condition in self.conditions
            if condition.must_display()
        ]
        return data
