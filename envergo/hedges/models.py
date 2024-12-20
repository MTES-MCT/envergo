import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

import requests
from django.conf import settings
from django.db import models
from pyproj import Geod
from shapely import LineString

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


@dataclass
class EvaluationResult:
    result: Literal["adequate", "inadequate"]
    conditions: list[str]


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

    def is_not_planting_under_power_line(self):
        """Returns True if there is NO hedges to plant, containing high-growing trees (type alignement or mixte),
        that are under power line"""
        return not any(
            h.hedge_type in ["alignement", "mixte"]
            and h.additionalData.get("sousLigneElectrique", False)
            for h in self.hedges_to_plant()
        )

    def minimum_length_to_plant(self):
        """Returns the minimum length of hedges to plant, considering the length of hedges to remove and the
        replantation coefficient"""
        return round(R * self.length_to_remove())

    def is_length_to_plant_sufficient(self):
        """Returns True if the length of hedges to plant is sufficient

        LP : longueur totale plantée
        LD : longueur totale détruite
        R : coefficient de replantation exigée

        Condition à remplir :
        LP ≥ R x LD
        """
        return self.length_to_plant() >= self.minimum_length_to_plant()

    def _get_minimum_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_remove in self.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        return {
            "degradee": R * lengths_by_type["degradee"],
            "buissonnante": R * lengths_by_type["buissonnante"],
            "arbustive": R * lengths_by_type["arbustive"],
            "mixte": R * lengths_by_type["mixte"],
            "alignement": R * lengths_by_type["alignement"],
        }

    def _get_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_plant in self.hedges_to_plant():
            lengths_by_type[to_plant.hedge_type] += to_plant.length

        return {
            "buissonnante": lengths_by_type["buissonnante"],
            "arbustive": lengths_by_type["arbustive"],
            "mixte": lengths_by_type["mixte"],
            "alignement": lengths_by_type["alignement"],
        }

    def evaluate_hedge_plantation_quality(self):
        url = f"{settings.PUBLICODES_SERVICE_URL}hedges/quality/"
        headers = {"Content-Type": "application/json"}
        data = {
            "minimum_lengths_to_plant": self._get_minimum_lengths_to_plant(),
            "lengths_to_plant": self._get_lengths_to_plant(),
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        quality_evaluation = self.evaluate_hedge_plantation_quality()

        conditions = {
            "length_to_plant": self.is_length_to_plant_sufficient(),
            "quality": quality_evaluation["isQualitySufficient"],
            "do_not_plant_under_power_line": self.is_not_planting_under_power_line(),
        }
        result = EvaluationResult(
            result="adequate" if all(conditions.values()) else "inadequate",
            conditions=[
                condition for condition in conditions if not conditions[condition]
            ],
        )
        return result
