import uuid

# from django.contrib.gis.geos import LineString
from django.db import models
from pyproj import Geod
from shapely import LineString

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"


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

    @property
    def proximite_mare(self):
        return self.additionalData.get("proximiteMare", None)

    @property
    def vieil_arbre(self):
        return self.additionalData.get("vieilArbre", None)

    @property
    def proximite_point_eau(self):
        return self.additionalData.get("proximitePointEau", None)

    @property
    def connexion_boisement(self):
        return self.additionalData.get("connexionBoisement", None)

    @property
    def sous_ligne_electrique(self):
        return self.additionalData.get("sousLigneElectrique", None)


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

    def hedges_to_remove_pac(self):
        return [
            h
            for h in self.hedges_to_remove()
            if h.is_on_pac and h.hedge_type != "alignement"
        ]

    def hedges_to_plant_pac(self):
        return [
            h
            for h in self.hedges_to_plant()
            if h.is_on_pac and h.hedge_type != "alignement"
        ]

    def lineaire_detruit_pac(self):
        return round(sum(h.length for h in self.hedges_to_remove_pac()))

    def lineaire_plante_pac(self):
        return round(sum(h.length for h in self.hedges_to_plant_pac()))

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

    def is_removing_near_pond(self):
        """Return True if at least one hedge to remove is near a pond."""
        return any(
            h.additionalData.get("proximiteMare", False)
            for h in self.hedges_to_remove()
        )

    def is_removing_old_tree(self):
        """Return True if at least one hedge to remove is containing old tree."""
        return any(
            h.additionalData.get("vieilArbre", False) for h in self.hedges_to_remove()
        )
