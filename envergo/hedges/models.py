import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

# from django.contrib.gis.geos import LineString
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

    def _get_length_to_compensate(self):
        lengths_by_type = defaultdict(int)
        for to_remove in self.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        return {
            "buissonnante": R
            * (lengths_by_type["degradee"] + lengths_by_type["buissonnante"]),
            "arbustive": R * lengths_by_type["arbustive"],
            "mixte": R * lengths_by_type["mixte"],
            "alignement": R * lengths_by_type["alignement"],
        }

    def is_planted_hedge_quality_sufficient(self):
        """Returns True if the quality of hedges to plant is sufficient

        Variables utilisées

            LD_i : linéaire détruit de type i
            LP_i : linéaire planté de type i (saisi dans l’interface)
            LPm_i : linéaire planté minimal de type i. Il se calcule ainsi :

            LPm_2 = R x (LD_1+LD_2) // (puisque 1 doit être remplacé au moins par du 2)
            LPm_3 = R x LD_3
            LPm_4 = R x LD_4
            LPm_5 = R x LD_5

        Conditions à remplir

            L’ensemble des conditions (R5), (R4), (R3) et (R2) doit être rempli :

            Remplacement des haies de type 5 :
            LP_5 ≥ LPm_5			(R5)

            Remplacement des haies de type 4 (par du 4 ou du 5) :
            LP_4 + LS_54 ≥ LPm_4		(R4)

            où  LS_54 = MAX(0, LP_5-LPm_5)  est le reliquat de type 5 après utilisation en remplacement de 5, et
            disponible en remplacement de haie de type 4

            Remplacement des haies de type 3 (par du 3 ou du 5) :
            LP_3 + LS_53 ≥ LPm_3		(R3)

            où  LS_53 = MAX(0, LS_54 - MAX(0,LPm_4-LP_4))  est le reliquat de type 5 après utilisation pour du 5 ou du
            4, et disponible en remplacement de haie de type 3

            Remplacement des haies de type 2 (par du 2, du 3 ou du 5) :
            LP_2 + LS_53 + LS_32 ≥ LPm_2	(R2)

            où LS_52 = MAX(0, LS_53 - MAX(0,LPm_3-LP_3))  est le reliquat de type 5 après utilisation pour du 5, du 4
            ou du 3, et disponible en remplacement de haie de type 2

            et LS_32 = MAX(0, LP_3 - LPm_3) est le reliquat de type 3 après utilisation en remplacement de 3, et
            disponible en remplacement de haie de type 2
        """
        pass

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        conditions = {
            "length_to_plant": self.is_length_to_plant_sufficient(),
            "do_not_plant_under_power_line": self.is_not_planting_under_power_line(),
        }
        result = EvaluationResult(
            result="adequate" if all(conditions.values()) else "inadequate",
            conditions=[
                condition for condition in conditions if not conditions[condition]
            ],
        )
        return result
