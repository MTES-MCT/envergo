import glob
import json
import logging
import re
import sys
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory

import numpy as np
import requests
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import Intersection, Length
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point
from django.contrib.gis.measure import Distance
from django.contrib.gis.utils.layermapping import LayerMapping
from django.core.serializers import serialize
from django.db import connection
from django.db.models import QuerySet, Sum
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _
from scipy.interpolate import griddata

from envergo.geodata.models import MAP_TYPES, Department, Line, Zone

logger = logging.getLogger(__name__)

EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


class CeleryDebugStream:
    """A sys.stdout proxy that also updates the celery task states.

    Django's LayerMapping does not offer any hook to update the long running
    import task. It does provides a way to print the task's progress, though,
    by offering a `stream` argument to the `save` method.
    """

    def __init__(self, task, expected_zones):
        self.task = task
        self.expected_zones = expected_zones

    def write(self, msg):
        sys.stdout.write(msg)

        # Find the number of processed results from progress message
        if msg.startswith("Processed"):
            match = re.findall(r"\d+", msg)
            nb_saved = int(match[1])
            progress = int(nb_saved / self.expected_zones * 100)

            # update task state
            task_msg = (
                f"{nb_saved} zones importées sur {self.expected_zones} ({progress}%)"
            )
            self.task.update_state(state="PROGRESS", meta={"msg": task_msg})


class CustomMapping(LayerMapping):
    """A custom LayerMapping that allows to pass extra arguments to the generated model."""

    def __init__(self, *args, **kwargs):
        self.extra_kwargs = kwargs.pop("extra_kwargs")
        super().__init__(*args, **kwargs)

    def feature_kwargs(self, feat):
        kwargs = super().feature_kwargs(feat)
        kwargs.update(self.extra_kwargs)

        # We extract map attributes to the `attributes` json model field
        fields = feat.fields
        attributes = {f: self.get_attribute(feat, f) for f in fields}
        kwargs["attributes"] = attributes
        return kwargs

    def get_attribute(self, feat, field):
        """Extract map attribute.

        We can define custom methods for specific fields.
        """
        if f"get_attribute_{field}" in dir(self):
            attr = getattr(self, f"get_attribute_{field}")(feat)
        else:
            attr = feat.get(field)
        return attr

    def get_attribute_especes(self, feat):
        raw_especes = feat.get("especes")
        especes = list(map(int, raw_especes.split(",")))
        return especes


@contextmanager
def extract_map(archive):
    """Returns the path to the map file.

    If this is a zipped shapefile, extract it to a temporary directory.
    """
    if archive.name.endswith(".zip"):
        with TemporaryDirectory() as tmpdir:
            logger.info("Extracting map zip file")
            zf = zipfile.ZipFile(archive)
            zf.extractall(tmpdir)

            logger.info("Find .shp file path")
            paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !

            try:
                shapefile = paths[0]
            except IndexError:
                raise ValueError(_("No .shp file found in archive"))

            yield shapefile

    elif archive.name.endswith(".gpkg"):
        if hasattr(archive, "temporary_file_path"):
            yield archive.temporary_file_path()

        # Local files also get an url, but its just unreachable
        elif hasattr(archive, "url") and archive.url.startswith("http"):
            yield archive.url
        else:
            yield archive.path

    else:
        raise ValueError(_("Unsupported file format"))


def count_features(map_file):
    """Count the number of features from a shapefile."""

    with extract_map(map_file) as file:
        ds = DataSource(file)
        layer = ds[0]
        nb_zones = len(layer)

    return nb_zones


def process_geographic_file(map, lm, task):
    if task:
        debug_stream = CeleryDebugStream(task, map.expected_geometries)
    else:
        debug_stream = sys.stdout

    logger.info("Calling layer mapping `save`")
    lm.save(strict=False, progress=True, stream=debug_stream)
    logger.info("Importing is done")


def process_zones_file(map, map_file, task=None):
    logger.info("Instanciating custom LayerMapping")
    mapping = {"geometry": "MULTIPOLYGON"}
    extra = {"map": map}
    lm = CustomMapping(
        Zone,
        map_file,
        mapping,
        transaction_mode="autocommit",
        extra_kwargs=extra,
    )

    process_geographic_file(map, lm, task)


def process_lines_file(map, map_file, task=None):
    logger.info("Instanciating custom LayerMapping")
    mapping = {"geometry": "LINESTRING"}
    extra = {"map": map}
    lm = CustomMapping(
        Line,
        map_file,
        mapping,
        transaction_mode="autocommit",
        extra_kwargs=extra,
    )

    process_geographic_file(map, lm, task)


def make_polygons_valid(map):
    """Run a postgis query to make sure all polygons are valid.

    This is to prevent errors with some GEOS operations, and avoid
    `TopologyException` errors.

    ST_MakeValid: fix polygons topology errors
    ST_CollectionExtract: Extract polygons from results (discards points and lines)
    ST_Multi: Make sure the result is a MultiPolygon
    """

    logger.info("Fixing invalid polygons")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM geodata_zone
            WHERE ST_IsValid(geometry::geometry) = False
            AND map_id = %s
            """,
            [map.id],
        )
        res = cursor.fetchone()
        logger.info(f"{res[0]} invalid polygons have been found")

        cursor.execute(
            """
            UPDATE geodata_zone
            SET geometry = ST_Multi(
              ST_CollectionExtract(
                ST_MakeValid(geometry::geometry, 'method=structure keepcollapsed=false'),
                3
              )
            )::geography
            WHERE ST_IsValid(geometry::geometry) = False
            AND map_id = %s
            """,
            [map.id],
        )
    logger.info("Invalid polygons have been fixed")


def to_geojson(obj, geometry_field="geometry"):
    """Return serialized geojson.

    Convert python objects to geojson, for leaflet display purpose.
    Two types of objects are supported:
     - queryset of models holding a geometry fields
     - GEOS geometry objects

    Leaflet expects geojson objects to have EPSG:WGS84 coordinates, so we
    make sure to make the conversion if geometries are stored in a different
    srid.
    """

    if isinstance(obj, (QuerySet, list)):
        geojson = serialize("geojson", obj, geometry_field=geometry_field)
    elif hasattr(obj, "geojson"):
        if obj.srid != EPSG_WGS84:
            obj = obj.transform(EPSG_WGS84, clone=True)
        geojson = obj.geojson
    else:
        raise ValueError(f"Cannot geojson serialize the given object {obj}")

    return json.loads(geojson)


def get_data_from_coords(lng, lat, timeout=0.5, index="address", limit=1):
    url = f"https://data.geopf.fr/geocodage/reverse?lon={lng}&lat={lat}&index={index}&limit={limit}"  # noqa

    if is_test():
        raise NotImplementedError("You should mock this function in tests")

    data = None
    try:
        logger.info("Requesting ign geocodage api", extra={"lng": lng, "lat": lat})
        res = requests.get(url, timeout=timeout)
        if res.status_code == 200:
            json = res.json()
            data = json["features"]
    except (
        requests.exceptions.RequestException,
        KeyError,
        IndexError,
    ) as e:
        logger.warning(
            "An error occured during the request to ign geocodage api",
            extra={"exception": e},
        )

    return data


def get_address_from_coords(lng, lat, timeout=0.5):
    """Use ign geocodage api to find address corresponding to coords.

    Returns None in case anything goes wrong with the request.
    """

    # try to find the address first, fallback on the parcel if not found to get at least the city and department
    data = get_data_from_coords(lng, lat, timeout, index="address,parcel", limit=5)
    address = None
    if data:
        for item in data:
            if item["properties"]["_type"] == "address":
                address = item["properties"]["label"]
                break
            if not address and item["properties"]["_type"] == "parcel":
                address = f"{item['properties']['city']} ({item['properties']['departmentcode']})"

    return address


def get_commune_from_coords(lng, lat, timeout=0.5):
    url = f"https://geo.api.gouv.fr/communes?lon={lng}&lat={lat}&fields=code,nom"

    if is_test():
        raise NotImplementedError("You should mock this function in tests")

    data = None
    try:
        res = requests.get(url, timeout=timeout)
        if res.status_code == 200:
            json = res.json()
            data = json[0]
    except (requests.exceptions.Timeout, KeyError, IndexError):
        pass

    return data["nom"] if data else None


def get_department_from_coords(lng, lat):
    """Get department code from lng lat"""
    lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
    department = Department.objects.filter(geometry__contains=lng_lat).first()

    return department.department if department else ""


def merge_geometries(polygons):
    """Return a single polygon that is the fusion of the given polygons."""

    merged = GEOSGeometry("POLYGON EMPTY", srid=4326)
    for polygon in polygons:
        try:
            merged = merged.union(
                polygon.simplify(preserve_topology=True, tolerance=0.0)
            )
        except:  # noqa
            pass

    return merged


def simplify_map(map):
    """Generates a simplified geometry for the entire map.

    This methods takes a map and generates a single polygon that is the union
    of all the polygons in the map.

    We also simplify the polygon because this is for display purpose only.

    We use native postgis methods those operations, because it's way faster.

    As for simplification, we don't preserve topology (ST_Simplify instead of
    ST_SimplifyPreserveTopology) because we want to be able to drop small
    holes in the polygon.

    Because of that, we also have to call ST_MakeValid to avoid returning invalid
    polygons.

    We wrap all of this in ST_CollectionExtract to make sure we get a MultiPolygon."""

    logger.info("Generating map preview polygon")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              ST_AsText(
                ST_Multi(
                  ST_CollectionExtract(
                    ST_MakeValid(
                      ST_Simplify(
                        ST_Union(ST_MakeValid(z.geometry::geometry)),
                        0.0001
                      ),
                      'method=structure keepcollapsed=false'
                    ),
                  3)
                )::geography
              )
              AS polygon
            FROM geodata_zone as z
            WHERE z.map_id = %s
            """,
            [map.id],
        )
        row = cursor.fetchone()

    polygon = GEOSGeometry(row[0], srid=EPSG_WGS84)
    if not isinstance(polygon, MultiPolygon):
        logger.error(
            f"The query did not generate the correct geometry type ({type(polygon)})"
        )

    logger.info("Preview generation is done")
    return polygon


def fill_polygon_stats():
    """Update the main obj with stats from the geometry field.

    This is only used manually when the need arises, for debugging purpose.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
        UPDATE geodata_zone
        SET
            area = ST_Area(geometry),
            npoints = ST_NPoints(geometry::geometry);
        """
        )


def get_catchment_area(lng, lat):
    """Return the catchment area of a point."""

    pixels = get_catchment_area_pixel_values(lng, lat)
    if not pixels:
        return None

    lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
    lamb93_coords = lng_lat.transform(EPSG_LAMB93, clone=True)

    coords = [(x, y) for x, y, v in pixels]
    values = [int(v) for x, y, v in pixels]
    interpolated_area = griddata(coords, values, lamb93_coords, method="linear")[0]
    if np.isnan(interpolated_area):
        interpolated_area = None

    return int(interpolated_area)


def get_catchment_area_pixel_values(lng, lat):
    # It took me a week to come up with the following queries, so here is
    # a bit of explanation.

    # In the database, we have a raster storing catchment area values for
    # various coordinates, arranged in a 20x20m grid, and stored in a
    # Lambert93 projection.
    # The user provides a lat/lng coordinate, and we want to know the
    # catchment area at this point.

    # Here is the catch: we don't just want to get the nearest value, since
    # there can be huge variations from one cell to the other.
    # So we have to use bilinear interpolaton to "smooth" the values.

    # I couldn't find a way to do this directly in PostGIS, so the actual
    # interpolation has to be performed in Python. It means we need to
    # fetch a grid of coordinates / values around the point from the db.

    # The usual raster querying methods ST_Value, ST_NearestValue and
    # ST_Neighborhood return value from the raster, but not the coordinates.
    # So we have to use the alternative ST_PixelAsPoints, which converts
    # the raster values into Point geometries, alongside the associated values.

    # To only get the relevant values, we clip the raster with a bounding box
    # around our point using ST_Clip(ST_Envelope(ST_Buffer(…
    pixels = []
    with connection.cursor() as cursor:
        query = """
        SELECT ST_X(geom), ST_Y(geom), val
        FROM (
            SELECT
            (ST_PixelAsPoints(
                ST_Clip(
                tiles.rast,
                envelope
                )
            )).*
            FROM
            geodata_catchmentareatile AS tiles
            CROSS JOIN
                ST_Transform(
                ST_Point(%s, %s, 4326),
                2154
            ) AS point
            CROSS JOIN
                ST_Envelope(
                ST_Buffer(point, 30)
                ) AS envelope
            WHERE
            ST_Intersects(tiles.rast, envelope)
            ) points;
        """
        cursor.execute(query, [lng, lat])
        pixels = cursor.fetchall()
    return pixels


def is_test():
    return "pytest" in sys.modules


def get_best_epsg_for_location(longitude, latitude) -> int:
    """
    Determine the most accurate EPSG code to use for geographical computation in meters,
    based on a location latitude and longitude.

    Returns:
        EPSG code as int (326xx for northern UTM, 327xx for southern UTM)
    """
    utm_zone = int((longitude + 180) / 6) + 1

    if latitude >= 0:
        epsg_code = 32600 + utm_zone  # Northern hemisphere
    else:
        epsg_code = 32700 + utm_zone  # Southern hemisphere

    return epsg_code


def trim_imerged_land(geom):
    """Keep only the part of the geometry that is in France and not in the sea.

    Django ORM does not support cumulative intersection (reduce(ST_Intersection)) across multiple geometries
    so it uses raw SQL
    Returns:
        - the intersection of the circle with the map zones
        - None if there is no intersection
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH input_poly AS (
              SELECT ST_GeomFromEWKT(%s) AS geom
            ),
            unioned_geom AS (
              SELECT ST_Union(z.geometry::geometry) AS merged_geom
              FROM geodata_zone z
              JOIN geodata_map m ON z.map_id = m.id
              JOIN input_poly i ON ST_Intersects(z.geometry, i.geom)
              WHERE m.map_type = %s
            )
            SELECT ST_AsText(ST_Intersection(u.merged_geom, i.geom))
            FROM unioned_geom u, input_poly i;
        """,
            [geom.ewkt, MAP_TYPES.terres_emergees],
        )
        wkt = cursor.fetchone()[0]
        if wkt:
            trimmed_geom = GEOSGeometry(wkt)
            trimmed_geom.srid = geom.srid  # Set SRID explicitly
        else:
            trimmed_geom = None
        return trimmed_geom


def compute_hedge_density_around_point(point_geos, radius):
    """Compute the density of hedges around a point."""

    # use specific projection to be able to use meters for buffering
    epsg_utm = get_best_epsg_for_location(point_geos.x, point_geos.y)
    centroid_meter = point_geos.transform(epsg_utm, clone=True)
    circle = centroid_meter.buffer(radius)

    circle = circle.transform(EPSG_WGS84, clone=True)  # switch back to WGS84

    # remove the sea from the circles
    truncated_circle = trim_imerged_land(circle)

    if truncated_circle:
        truncated_circle_m = truncated_circle.transform(
            epsg_utm, clone=True
        )  # use specific projection to compute the area in square meters

        area = truncated_circle_m.area
        area_ha = area * 0.0001

        # get the length of the hedges in the circles
        length = (
            Line.objects.filter(
                geometry__intersects=truncated_circle,
                map__map_type=MAP_TYPES.haies,
            )
            .annotate(clipped=Intersection("geometry", truncated_circle))
            .annotate(length=Length(Cast("clipped", GeometryField())))
            .aggregate(total=Sum("length"))["total"]
        )
        length = length if length else Distance(0)

        density = length.standard / area_ha if area_ha > 0 else 1000.0
    else:
        # there is no land in the circle (e.g. sea or foreign country)
        length = Distance(0)
        area_ha = 0.0
        density = 1000.0

    return {
        "density": density,
        "artifacts": {
            "truncated_circle": truncated_circle,
            "length": length.standard,
            "area_ha": area_ha,
        },
    }
