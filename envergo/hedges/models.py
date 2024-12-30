import uuid
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

from django.db import models
from pyproj import Geod
from shapely import LineString

from envergo.evaluations.models import RESULTS

if TYPE_CHECKING:
    from envergo.moulinette.models import MoulinetteHaie

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"

R = 2  # Coefficient de replantation exigée

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857

EPSG_LAMB93 = 2154


class Hedge:
    """Represent a single hedge."""

    def __init__(self, id, latLngs, type, additionalData=None):
        self.id = id  # The edge reference, e.g A1, A2…
        self.geometry = LineString(
            [(latLng["lng"], latLng["lat"]) for latLng in latLngs]
        )
        self.type = type
        self.additionalData = additionalData or {}

    @property
    def length(self):
        """Returns the geodesic length (in meters) of the line."""

        geod = Geod(ellps="WGS84")
        length = geod.geometry_length(self.geometry)
        return length

    @property
    def is_on_pac(self):
        return self.additionalData.get("surParcellePac", False)

    @property
    def hedge_type(self):
        return self.additionalData.get("typeHaie", None)


class HedgeData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    class Meta:
        verbose_name = "Hedge data"
        verbose_name_plural = "Hedge data"

    def __str__(self):
        return str(self.id)

    def __iter__(self):
        return iter(self.hedges())

    def hedges(self):
        return [Hedge(**h) for h in self.data]

    def hedges_to_plant(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_PLANT]

    def length_to_plant(self):
        return round(sum(h.length for h in self.hedges_to_plant()))

    def hedges_to_remove(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_REMOVE]

    def length_to_remove(self):
        return round(sum(h.length for h in self.hedges_to_remove()))

    def lineaire_detruit_pac(self):
        return round(
            sum(
                h.length
                for h in self.hedges_to_remove()
                if h.is_on_pac and h.hedge_type != "alignement"
            )
        )

    def lineaire_detruit_pac_including_alignement(self):
        return round(sum(h.length for h in self.hedges_to_remove() if h.is_on_pac))

    def lineaire_type_4_sur_parcelle_pac(self):
        return round(
            sum(
                h.length
                for h in self.hedges_to_remove()
                if h.is_on_pac and h.hedge_type == "alignement"
            )
        )

    def minimum_length_to_plant(self):
        """Returns the minimum length of hedges to plant, considering the length of hedges to remove and the
        replantation coefficient"""
        return round(R * self.length_to_remove())


class PlantationResults(Enum):
    Adequate = "adequate"
    Inadequate = "inadequate"


class PlantationEvaluator:

    def __init__(self, moulinette: "MoulinetteHaie", hedge_data: HedgeData):
        self.moulinette = moulinette
        self.hedge_data = hedge_data
        self.evaluate()

    @dataclass
    class EvaluationResult:
        result: Literal[PlantationResults.Adequate, PlantationResults.Inadequate]
        conditions: list[str]

    @property
    def result(self):
        """Return the evaluator result.

        This value is used to rendered the plantation result templates.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._evaluation_result.result.value

    @property
    def global_result(self):
        """Return the project result combining both removal and plantation.

        This value is used to rendered the plantation result templates.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        result_matrix = {
            (RESULTS.interdit, PlantationResults.Inadequate.value): RESULTS.interdit,
            (RESULTS.interdit, PlantationResults.Adequate.value): RESULTS.interdit,
            (
                RESULTS.soumis,
                PlantationResults.Inadequate.value,
            ): PlantationResults.Inadequate.value,
            (RESULTS.soumis, PlantationResults.Adequate.value): RESULTS.soumis,
        }

        return result_matrix.get(
            (self.moulinette.result, self.result), RESULTS.interdit
        )

    @property
    def result_code(self):
        """Return the plantation evaluator result code.

        The result code is a unique code used to render the criterion template.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return f"{self.moulinette.result}_{self.result}"

    @property
    def unfulfilled_conditions(self):
        """Return the list of conditions that are not met to make the plantation project adequate."""
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._evaluation_result.conditions

    def is_not_planting_under_power_line(self):
        """Returns True if there is NO hedges to plant, containing high-growing trees (type alignement or mixte),
        that are under power line"""
        return not any(
            h.hedge_type in ["alignement", "mixte"]
            and h.additionalData.get("sousLigneElectrique", False)
            for h in self.hedge_data.hedges_to_plant()
        )

    def is_length_to_plant_sufficient(self):
        """Returns True if the length of hedges to plant is sufficient

        LP : longueur totale plantée
        LD : longueur totale détruite
        R : coefficient de replantation exigée

        Condition à remplir :
        LP ≥ R x LD
        """
        return (
            self.hedge_data.length_to_plant()
            >= self.hedge_data.minimum_length_to_plant()
        )

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        conditions = {
            "length_to_plant": self.is_length_to_plant_sufficient(),
            "do_not_plant_under_power_line": self.is_not_planting_under_power_line(),
        }
        result = self.EvaluationResult(
            result=(
                PlantationResults.Adequate
                if all(conditions.values())
                else PlantationResults.Inadequate
            ),
            conditions=[
                condition for condition in conditions if not conditions[condition]
            ],
        )

        self._evaluation_result = result
        return result
