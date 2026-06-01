from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal as D
from enum import Enum
from functools import cmp_to_key
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
    (
        RESULTS.action_requise,
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    (RESULTS.action_requise, PlantationResults.Adequate.value): RESULTS.action_requise,
    (
        "autorisation",
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    ("autorisation", PlantationResults.Adequate.value): "autorisation",
    (
        "declaration",
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    ("declaration", PlantationResults.Adequate.value): "declaration",
    # not used for now:
    (
        RESULTS.non_disponible,
        PlantationResults.Inadequate.value,
    ): RESULTS.non_disponible,
    (RESULTS.non_disponible, PlantationResults.Adequate.value): RESULTS.non_disponible,
}

DISPLAY_FOR_ALTERNATIVES_MATRIX = {
    RESULTS.interdit: True,
    RESULTS.soumis: False,
    RESULTS.non_soumis: False,
    RESULTS.action_requise: False,
    PlantationResults.Inadequate.value: True,
    RESULTS.non_disponible: True,
    "autorisation": False,
    "declaration": False,
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

_missing_results = set(
    key
    for key in PLANTATION_RESULT_MATRIX.values()
    if key not in DISPLAY_FOR_ALTERNATIVES_MATRIX
)
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in DISPLAY_FOR_ALTERNATIVES_MATRIX: {_missing_results}"
    )


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
    hedges_5000_mls = []

    for hedge in hedges_5000:
        geom = hedge.geometry

        if not geom:
            continue

        hedges_5000_mls.extend(geom)

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
                        hedges_5000_mls,
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


def create_line_buffer_density_map(
    hedges_to_remove, truncated_buffer_zone, buffer_zone
):
    """Build a Leaflet map showing line-buffer density artifacts.

    Similar to `create_density_map` but for line-buffer (400 m) density
    instead of centroid-based density.
    """
    display_zone = truncated_buffer_zone or buffer_zone

    if len(hedges_to_remove) == 0 or not display_zone:
        return None

    existing_lines = Line.objects.filter(
        map__map_type=MAP_TYPES.haies,
        geometry__intersects=display_zone,
    )
    existing_mls = []
    for line in existing_lines:
        geom = line.geometry
        if not geom:
            continue
        existing_mls.extend(geom)

    centroid = hedges_to_remove[0].geos_geometry.centroid

    entries = [
        MapPolygon(
            [SimpleNamespace(geometry=display_zone)],
            "#457EAC",
            "Zone tampon 400 m",
        ),
        MapPolygon(
            [SimpleNamespace(geometry=MultiLineString(existing_mls, srid=EPSG_WGS84))],
            "#f0f921",
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
        center=centroid,
        entries=entries,
        truncate=False,
        display_marker_at_center=False,
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
        """Deduplicated subset — when several evaluators produce the same condition
        class, only the strictest is kept. See ``all_conditions`` for the full list.
        """
        if not hasattr(self, "_conditions"):
            self.evaluate()

        return self._conditions

    @property
    def all_conditions(self):
        """Full list before deduplication, used when the caller needs to
        disambiguate by evaluator. See ``conditions`` for the deduplicated subset.
        """
        if not hasattr(self, "_all_conditions"):
            self.evaluate()

        return self._all_conditions

    @property
    def global_result(self):
        """Return the project result combining both removal and plantation.

        This value is used to select the plantation result templates.
        """
        return PLANTATION_RESULT_MATRIX.get(
            (self.moulinette.result, self.result), RESULTS.interdit
        )

    @property
    def display_for_alternatives(self):
        """Should this evaluation global result be displayed for project alternatives?"""
        return DISPLAY_FOR_ALTERNATIVES_MATRIX[self.global_result]

    @property
    def result_code(self):
        """Return the plantation evaluator result code.

        The result code is a unique code used to render the criterion template.
        """
        return f"{self.moulinette.result}_{self.result}"

    def evaluate(self):
        """Populate ``_all_conditions``, ``_conditions`` (deduplicated), and ``_result``."""

        R = self.replantation_coefficient
        conditions = []
        for regulation in self.moulinette.regulations:
            if not regulation.is_activated():
                continue

            if regulation.has_perimeters:
                all_perimeters = regulation.perimeters.all()
                activated_perimeters = [p for p in all_perimeters if p.is_activated]
                if not all_perimeters or not any(activated_perimeters):
                    continue

            for criterion in regulation.criteria.all():
                if hasattr(criterion._evaluator, "plantation_evaluate"):
                    conditions.extend(
                        criterion._evaluator.plantation_evaluate(
                            self.hedge_data, R, self.moulinette.catalog
                        )
                    )

        # We make sure the "min length condition" exists if it was not explicitely
        # added by an evaluator.
        has_min_length_condition = False
        for condition in conditions:
            if isinstance(condition, MinLengthCondition):
                has_min_length_condition = True
                break
        if not has_min_length_condition:
            conditions.append(
                MinLengthCondition(self.hedge_data, R, None, None).evaluate()
            )

        all_displayable = sorted(
            [c for c in conditions if c.result is not None and c.must_display()],
            key=attrgetter("order"),
        )
        self._all_conditions = all_displayable
        self._conditions = self.deduplicate_conditions(all_displayable)
        self._result = (
            PlantationResults.Adequate.value
            if len(self.invalid_conditions) == 0
            else PlantationResults.Inadequate.value
        )

    @staticmethod
    def deduplicate_conditions(conditions):
        """When all conditions in a group tie (no compare_strictness override),
        the first one in evaluator iteration order wins.
        """
        groups = defaultdict(list)
        for condition in conditions:
            groups[type(condition)].append(condition)

        def strictness_cmp(a, b):
            if a.is_stricter_than(b):
                return 1
            if b.is_stricter_than(a):
                return -1
            return 0

        return [max(group, key=cmp_to_key(strictness_cmp)) for group in groups.values()]

    def find_condition(self, condition_cls, evaluator=None):
        """Searches ``all_conditions`` so per-regulation views can locate a
        specific evaluator's condition even after deduplication. Evaluator
        filtering uses identity (``is``), so caller and condition must share
        the same moulinette instance.
        """
        for condition in self.all_conditions:
            if not isinstance(condition, condition_cls):
                continue
            if evaluator is None or condition.criterion_evaluator is evaluator:
                return condition
        return None

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
                "hint": condition.hint,
                "result": condition.result,
                "text": condition.text,
                "context": condition.context,
            }
            for condition in self.conditions
        ]
        return data
