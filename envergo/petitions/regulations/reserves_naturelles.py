import shapely
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import MultiLineString
from django.db.models.functions import Cast
from pyproj import Geod

from envergo.geodata.constants import EPSG_WGS84
from envergo.hedges.models import Hedge, HedgeList
from envergo.moulinette.regulations.reserves_naturelles import (
    ReservesNaturellesRegulation,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


class HedgeInZone(Hedge):
    """A Hedge whose `length` is the length of its intersection with a set of zones, instead of its full length."""

    def __init__(self, hedge, length_in_zone):
        self.__dict__.update(hedge.__dict__)
        self._length_in_zone = length_in_zone

    @property
    def length(self):
        return self._length_in_zone


@evaluator_instructor_view_context_getter(ReservesNaturellesRegulation)
def reserves_naturelles_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for réserves naturelles regulation instructor view."""

    hedges = HedgeList()

    for (
        regulation,
        perimeters,
    ) in moulinette.hedges_intersecting_regulations_perimeter.items():
        if regulation.slug != "reserves_naturelles":
            continue

        for perimeter, hedges_by_type in perimeters.items():
            # hedges_by_type's lists are already sorted by hedge id; keep that
            # order so the summary table's hedge names are stable.
            perimeter_hedges = HedgeList(
                sorted(
                    (
                        hedge
                        for hedge_list in hedges_by_type.values()
                        for hedge in hedge_list
                    ),
                    key=lambda h: h.id,
                )
            )
            hedges += get_hedges_length_in_zones(perimeter, perimeter_hedges)

    return {
        "reserves_naturelles_hedges": hedges,
    }


def get_hedges_length_in_zones(perimeter, hedges):
    """Return `hedges`, decorated with the length of their intersection with
    the perimeter's zones instead of their full geometry length.

    Covers both hedges to remove and hedges to plant, so the resulting
    HedgeList fits directly into hedges/_hedge_summary_table.html.
    """
    if not hedges:
        return HedgeList()

    hedges_geom = MultiLineString([h.geos_geometry for h in hedges], srid=EPSG_WGS84)

    # Find all the Zones for the current Perimeter that intersect any of the hedges
    qs = (
        perimeter.activation_map.zones.all()
        .filter(geometry__intersects=hedges_geom)
        .aggregate(geom=Union(Cast("geometry", MultiPolygonField())))
    )
    # Aggregate them into a single polygon.
    # Union returns None when no zones match the filter.
    multipolygon = qs["geom"]
    if multipolygon is None:
        return HedgeList()

    # Other conversion options throw a cryptic numpy error, so…
    geom = shapely.from_wkt(multipolygon.wkt)

    # Use the geodesic length
    geod = Geod(ellps="WGS84")

    return HedgeList(
        HedgeInZone(hedge, geod.geometry_length(hedge.geometry.intersection(geom)))
        for hedge in hedges
    )
