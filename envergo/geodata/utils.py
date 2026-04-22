import glob
import json
import logging
import re
import sys
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import numpy as np
import requests
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiLineString, MultiPolygon, Point
from django.contrib.gis.utils.layermapping import LayerMapping
from django.core.serializers import serialize
from django.db import connection
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from scipy.interpolate import griddata

from envergo.geodata.models import MAP_TYPES, Department, Line, Zone

if TYPE_CHECKING:
    from envergo.hedges.models import HedgeData

logger = logging.getLogger(__name__)

EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


def parse_jsonb(value):
    """Normalize a jsonb value from a raw DB cursor to a Python dict.

    Django's raw cursor may return jsonb columns as strings rather than
    dicts, depending on the psycopg adapter configuration.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value

FRANCE_LAT = 46.76305599999998
FRANCE_LNG = 2.424722
FRANCE_ZOOM = 6
IGN_URL = "https://www.geoportail.gouv.fr/carte?c={0},{1}&z={2}&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&l1=LIMITES_ADMINISTRATIVES_EXPRESS.LATEST::GEOPORTAIL:OGC:WMTS(1)&l2=hedge.hedge::GEOPORTAIL:OGC:WMTS(1)&permalink=yes"  # noqa
GOOGLE_MAPS_URL = (
    "https://www.google.com/maps/@?api=1&map_action=map&center={1},{0}&zoom={2}"
)
GEOPORTAIL_URL = (
    "https://www.geoportail-urbanisme.gouv.fr/map/#tile=1&lon={0}&lat={1}&zoom={2}"
)


ATTRIBUTES = {
    "especes": "species_taxrefs",
}


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
            if self.expected_zones > 0:
                progress = int(nb_saved / self.expected_zones * 100)
            else:
                progress = 0

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

        for field in fields:
            if field in ATTRIBUTES:
                kwargs[ATTRIBUTES[field]] = self.get_attribute(feat, field)

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
        especes = list(map(int, filter(None, raw_especes.split(","))))
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
        elif hasattr(archive, "path"):
            yield archive.path
        else:
            yield archive.name

    else:
        raise ValueError(_("Unsupported file format"))


def count_features(map_file):
    """Count the number of features from a shapefile."""

    with extract_map(map_file) as file:
        ds = DataSource(file)
        layer = ds[0]
        nb_features = len(layer)

    return nb_features


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
    mapping = {"geometry": "MULTILINESTRING"}
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


def simplify_lines(map):
    """Generates a simplified MultiLineString for the entire map.

    It uses the sames algorithms as `simplify_map`, but for lines instead of polygons.
    """

    logger.info("Generating map preview as MultiLineString")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              ST_AsText(
                ST_Multi(
                  ST_CollectionExtract(
                    ST_MakeValid(
                      ST_Simplify(
                        ST_Union(ST_MakeValid(l.geometry::geometry)),
                        0.0001
                      ),
                      'method=structure keepcollapsed=false'
                    ),
                  2)
                )::geography
              )
              AS lines
            FROM geodata_line as l
            WHERE l.map_id = %s
            """,
            [map.id],
        )
        row = cursor.fetchone()

    lines = GEOSGeometry(row[0], srid=EPSG_WGS84)
    if not isinstance(lines, MultiLineString):
        logger.error(
            f"The query did not generate the correct geometry type ({type(lines)})"
        )

    logger.info("Preview generation is done")
    return lines


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


def trim_land(geom):
    """Keep only the part of the geometry that is in France and not in the sea.

    Django ORM does not support cumulative intersection (reduce(ST_Intersection))
    across multiple geometries so this uses raw SQL.

    How the query works:

     - Select all the "Terres emergées" polygons that intersect the geometry
     - Clip the polygons to the geometry bounding box (cheap operation)
     - Merge the remaining polygons
     - Intersects the merged polygon with the input geometry

    The clipping step is an optimization: it reduces the size of the polygons
    before merging them (which is a costly operation).

    Returns:
        - the intersection of the input geometry with the union of land zones
        - None if there is no intersection (input is entirely off-land)
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH input_poly AS (
              SELECT
                ST_GeomFromEWKT(%s) AS geom,
                ST_Envelope(ST_GeomFromEWKT(%s)) AS bbox
            ),
            clipped AS (
              SELECT ST_MakeValid(ST_ClipByBox2D(z.geometry::geometry, i.bbox)) AS g
              FROM geodata_zone z
              JOIN geodata_map m ON z.map_id = m.id
              JOIN input_poly i ON ST_Intersects(z.geometry, i.geom)
              WHERE m.map_type = %s
            ),
            unioned_geom AS (
              SELECT ST_Union(g) AS merged
              FROM clipped
              WHERE NOT ST_IsEmpty(g)
            )
            SELECT ST_AsText(
                ST_CollectionExtract(ST_Intersection(u.merged, i.geom), 3)
            )
            FROM unioned_geom u, input_poly i;
        """,
            [geom.ewkt, geom.ewkt, MAP_TYPES.terres_emergees],
        )
        wkt = cursor.fetchone()[0]
        if wkt:
            trimmed_geom = GEOSGeometry(wkt)
            trimmed_geom.srid = geom.srid  # Set SRID explicitly
        else:
            trimmed_geom = None
        return trimmed_geom


WGS84_SPHEROID = 'SPHEROID["WGS 84",6378137,298.257223563]'


def query_hedge_length(truncated_buffer, untruncated_circle):
    """Sum the clipped hedge length inside a buffer.

    We need to compute lengths of hedges clipped to the circle, BUT running
    ST_Intersection on every hedge is expensive. In many cases, most hedges
    are fully INSIDE the circle.

    So we use a CASE statement, and only run the intersection when the hedge
    is not fully inside the circle.

    In a simulation with heavy hedge density, it significantly improves the query perf.

    Args:
        truncated_buffer: land-trimmed polygon, or None if off-land.
        untruncated_circle: the raw circle before land trimming. Used for
            row filtering (WHERE) and as a fast containment check.

    Returns length in meters (float).
    """

    if truncated_buffer is None or truncated_buffer.empty:
        return 0.0

    circle_ewkt = untruncated_circle.ewkt
    sql = f"""
        SELECT COALESCE(SUM(CASE
            WHEN ST_CoveredBy(l.geometry, ST_GeomFromEWKT(%s))
            THEN ST_LengthSpheroid(
                l.geometry::geometry(GEOMETRY,4326), '{WGS84_SPHEROID}')
            ELSE ST_LengthSpheroid(
                ST_Intersection(l.geometry, ST_GeomFromEWKT(%s))
                ::geometry(GEOMETRY,4326), '{WGS84_SPHEROID}')
        END), 0)
        FROM geodata_line l
        JOIN geodata_map m ON l.map_id = m.id
        WHERE m.map_type = %s
          AND ST_Intersects(l.geometry, ST_GeomFromEWKT(%s));
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            [
                circle_ewkt,
                truncated_buffer.ewkt,
                MAP_TYPES.haies,
                circle_ewkt,
            ],
        )
        return cursor.fetchone()[0]


def query_hedges_display_geojson(buffer_geos, simplify_tolerance):
    """Return simplified hedge geometries inside `buffer_geos` as GeoJSON.

    Returns a parsed MultiLineString dict, or None if no haies match.
    ST_Multi wraps the ST_Collect result to guarantee MultiLineString
    output (ST_Collect alone can return GeometryCollection).

    This is a separate query from `query_hedge_lengths_for_buffers` because
    combining them into a single scan was empirically ~430 ms slower.
    """

    sql = """
        SELECT ST_AsGeoJSON(ST_Multi(ST_Collect(
            ST_SimplifyPreserveTopology(l.geometry::geometry, %(tol)s)
        )))
        FROM geodata_line l
        JOIN geodata_map m ON l.map_id = m.id
        WHERE m.map_type = %(map_type)s
          AND ST_Intersects(l.geometry, ST_GeomFromEWKT(%(buffer)s));
    """
    params = {
        "tol": simplify_tolerance,
        "map_type": MAP_TYPES.haies,
        "buffer": buffer_geos.ewkt,
    }
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        raw = cursor.fetchone()[0]
    if raw is None:
        return None
    return json.loads(raw)


def build_circles(point_geos, radii):
    """Build WGS84 circle polygons for each radius by buffering in UTM."""

    epsg_utm = get_best_epsg_for_location(point_geos.x, point_geos.y)
    centroid_m = point_geos.transform(epsg_utm, clone=True)
    circles = {r: centroid_m.buffer(r).transform(EPSG_WGS84, clone=True) for r in radii}
    return circles, epsg_utm


def trim_circles_to_land(circles):
    """Trim each circle to land, calling `trim_land` only once (on the largest).

    Smaller truncated circles are derived via GEOS intersection with the
    largest result, which is mathematically equivalent to calling
    `trim_land` on each circle individually.

    Returns {radius: truncated_geom | None}.
    """

    max_r = max(circles)
    truncated_max = trim_land(circles[max_r])
    if truncated_max is None:
        return {r: None for r in circles}

    result = {}
    for r in circles:
        if r == max_r:
            result[r] = truncated_max
            continue
        t = truncated_max.intersection(circles[r])
        if t.empty:
            result[r] = None
        else:
            t.srid = EPSG_WGS84
            result[r] = t
    return result


def area_in_ha(geom, epsg_utm):
    """Compute area in hectares by projecting to the given UTM zone."""

    if geom is None:
        return 0.0
    return geom.transform(epsg_utm, clone=True).area * 0.0001


def compute_hedge_densities_around_point(
    point_geos,
    radii,
    *,
    display_simplify_tolerance=None,
):
    """Compute hedge density at multiple concentric radii around a point.

    For the given point, for each radius:
     - build a circle polygon
     - trim it to land (sea excluded)
     - get the hedges length inside that circle
     - divide length by land area to get density

    Returns {radius: {"density", "artifacts": {...}}, "display_geojson": ...}.
    Off-land radii get the sentinel (density=1.0, length=0, area_ha=0).
    """

    if not radii:
        raise ValueError("radii must be a non-empty iterable")
    radii = list(radii)

    # Build the multiple land-intersecting circle geometries
    circles, epsg_utm = build_circles(point_geos, radii)
    truncated = trim_circles_to_land(circles)
    max_circle = circles[max(radii)]

    # One length query per radius, each focused on its own hedge set
    lengths = {r: query_hedge_length(truncated[r], circles[r]) for r in radii}

    # Build the result dict
    result = {}
    for r in radii:
        ha = area_in_ha(truncated[r], epsg_utm)
        density = lengths[r] / ha if truncated[r] and ha > 0 else 1.0
        result[r] = {
            "density": density,
            "artifacts": {
                "circle": circles[r],
                "truncated_circle": truncated[r],
                "length": lengths[r],
                "area_ha": ha,
            },
        }

    # Run a distinct query for the hedges lines to display with leaflet
    # It's quicker and lighter to display simplified geometries
    if display_simplify_tolerance is not None:
        result["display_geojson"] = query_hedges_display_geojson(
            max_circle, display_simplify_tolerance
        )

    return result


def compute_hedge_density_around_lines(
    line_geos, radius, *, display_simplify_tolerance=None
):
    """Compute the density of hedges in buffer radius.

    If `display_simplify_tolerance` is set, `artifacts` also contains a
    `display_geojson` key with the simplified hedges inside the buffer.
    """

    line_centroid = line_geos.centroid
    epsg_utm = get_best_epsg_for_location(line_centroid.x, line_centroid.y)
    line_meter = line_geos.transform(epsg_utm, clone=True)
    buffer_zone = line_meter.buffer(radius)
    buffer_zone = buffer_zone.transform(EPSG_WGS84, clone=True)

    truncated = trim_land(buffer_zone)
    length_m = query_hedge_length(truncated, buffer_zone)
    ha = area_in_ha(truncated, epsg_utm)
    density = length_m / ha if truncated and ha > 0 else 1.0

    artifacts = {
        "buffer_zone": buffer_zone,
        "truncated_buffer_zone": truncated,
        "length": length_m,
        "area_ha": ha,
    }

    if display_simplify_tolerance is not None:
        artifacts["display_geojson"] = query_hedges_display_geojson(
            buffer_zone, display_simplify_tolerance
        )

    return {"density": density, "artifacts": artifacts}


def _get_centered_url(url, hedges: "HedgeData"):
    lng = FRANCE_LNG
    lat = FRANCE_LAT
    zoom = FRANCE_ZOOM

    if hedges:
        # Generate urls centered on the project
        centroid = hedges.get_centroid_to_remove()
        lng = centroid.x
        lat = centroid.y
        zoom = 16

    return url.format(lng, lat, zoom)


def get_google_maps_centered_url(hedges: "HedgeData"):
    """Return the GoogleMaps URL centered on the hedges to remove."""
    return _get_centered_url(GOOGLE_MAPS_URL, hedges)


def get_ign_centered_url(hedges: "HedgeData"):
    """Return the IGN URL centered on the hedges to remove."""
    return _get_centered_url(IGN_URL, hedges)


def get_geoportail_urbanisme_centered_url(hedges: "HedgeData"):
    """Return the Geoportail de l'urbanisme url centered on the hedges to remove."""
    url = _get_centered_url(GEOPORTAIL_URL, hedges)
    if hedges:
        url += "&lowscale=0:0.7&municipality=0:0.7&document=0:0.7&zone_secteur,zone_secteur_psmv=0:0.7&du,psmv=1:0.7&info,info_psmv01020304050607080910111213141516171819202122232425262728293031323334353637383940414270979899=0:0.7&info,info_psmv98=0:0.7&info,info_psmv010203040506070809101112131415161718192021222324252627282930313233343536373839404142709799=0:0.7&prescription,prescription_psmv2217233006363743=0:0.7&prescription,prescription_psmv=1:0.7&prescription2217233006363743=0:0.7&prescription_psmv2217233006363743=0:0.7&prescription,prescription_psmv03041115162029383940414445=0:0.7&prescription03041115162029383940414445=0:0.7&prescription_psmv03041115162029383940414445=0:0.7&prescription,prescription_psmv141849=0:0.7&prescription141849=0:0.7&prescription_psmv141849=0:0.7&prescription,prescription_psmv0509102112242627284748=0:0.7&prescription0509102112242627284748=0:0.7&prescription_psmv0509102112242627284748=0:0.7&prescription,prescription_psmv0213195051=0:0.7&prescription0213195051=0:0.7&prescription_psmv0213195051=0:0.7"  # noqa

    return url
