import uuid

from django.contrib.gis.geos import LineString
from django.db import models

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"


# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


class Hedge:
    """Represent a single hedge."""

    def __init__(self, id, latLngs, type):
        self.id = id  # The edge reference, e.g A1, A2…
        self.geometry = LineString(
            [(latLng["lat"], latLng["lng"]) for latLng in latLngs], srid=EPSG_WGS84
        )
        self.geometry.transform(EPSG_MERCATOR)
        self.type = type

    @property
    def length(self):
        """TODO this gives a different value than leaflet. Need to investigate more."""

        return int(self.geometry.length)


class HedgeData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    class Meta:
        verbose_name = "Hedge data"
        verbose_name_plural = "Hedge data"

    def hedges(self):
        return [Hedge(**h) for h in self.data]

    def hedges_to_plant(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_PLANT]

    def length_to_plant(self):
        return sum(h.length for h in self.hedges_to_plant())

    def hedges_to_remove(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_REMOVE]

    def length_to_remove(self):
        return sum(h.length for h in self.hedges_to_remove())
