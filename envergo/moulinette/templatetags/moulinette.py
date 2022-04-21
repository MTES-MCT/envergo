from django import template
from django.core.serializers import serialize
from django.db.models import QuerySet
from django.utils.safestring import mark_safe

from envergo.moulinette.models import EPSG_WGS84

register = template.Library()


@register.simple_tag
def to_geojson(obj, geometry_field="geometry"):
    """Return serialized geojson.

    This is a unique template tag to convert python objects to geojson.
    Two types of objects are supported:
     - queryset of models holding a geometry fields
     - GEOS geometry objects

    Leaflet expects geojson objects to have EPSG:WGS84 coordinates, so we
    make sure to make the conversion if geometries are stored in a different
    srid.
    """

    if isinstance(obj, QuerySet):
        geojson = serialize("geojson", obj, geometry_field=geometry_field)
    elif hasattr(obj, "geojson"):
        if obj.srid != EPSG_WGS84:
            obj = obj.transform(EPSG_WGS84, clone=True)
        geojson = obj.geojson
    else:
        raise ValueError(f"Cannot geojson serialize the given object {obj}")

    return mark_safe(geojson)
