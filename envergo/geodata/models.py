import logging

from django.contrib.gis.db import models as gis_models
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.postgres.fields import ArrayField
from django.db import connection, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from localflavor.fr.fr_department import DEPARTMENT_CHOICES_PER_REGION
from model_utils import Choices

logger = logging.getLogger(__name__)


#: A list of departments
DEPARTMENT_CHOICES = tuple(
    [(dep[0], f"{dep[1]} ({dep[0]})") for dep in DEPARTMENT_CHOICES_PER_REGION]
)


MAP_TYPES = Choices(
    ("zone_humide", _("Zone humide")),
    ("zone_inondable", _("Zone inondable")),
    ("species", _("Espèces protégées")),
    ("haies", "Haies"),
    ("terres_emergees", "Délimitation terres + France"),
    ("zonage", "Identifiant zonage"),
    ("zone_sensible_ep", "Zone sensible EP"),
)

# Sometimes, there are map with different certainty values.
# E.g "this map represents zones that are wetlands for certain.
# This other map represents zones that are *maybe* wetlands.
DATA_TYPES = Choices(
    ("certain", _("Certain")), ("uncertain", _("Uncertain")), ("forbidden", "Interdit")
)


STATUSES = Choices(
    ("success", _("Success")),
    ("partial_success", _("Partial success")),
    ("failure", _("Failure")),
)


class Map(models.Model):
    """Holds a map file (shapefile / gpkg)."""

    name = models.CharField(_("Name"), max_length=256)
    display_name = models.CharField(_("Display name"), max_length=256, blank=True)
    source = models.URLField(_("Source"), max_length=2000, blank=True)
    display_for_user = models.BooleanField(_("Display for user?"), default=True)
    file = models.FileField(_("File"), upload_to="maps/")
    map_type = models.CharField(
        _("Map type"), max_length=50, choices=MAP_TYPES, blank=True
    )
    data_type = models.CharField(
        _("Data type"),
        max_length=20,
        choices=DATA_TYPES,
        default=DATA_TYPES.certain,
    )
    description = models.TextField(_("Description"))
    departments = ArrayField(
        verbose_name=_("Departments"),
        help_text=_("Select departments ids separated by commas"),
        null=True,
        blank=True,
        base_field=models.CharField(
            max_length=3,
            choices=DEPARTMENT_CHOICES,
        ),
    )
    # `geography=True`: query with __covers/__coveredby/__intersects, NOT
    # __contains/__within/__overlaps (silent cast to geometry bypasses the
    # GIST index → seq scans).
    geometry = gis_models.GeometryField(
        _("Simplified geometry"),
        help_text=_(
            """DO NOT EDIT! We cannot easily deactivate this edition widget,
            but if you use it, you will break Envergo.
            """
        ),
        geography=True,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    expected_geometries = models.IntegerField(
        "Nb de formes (zones ou lignes) attendues", default=0
    )
    imported_geometries = models.IntegerField(
        "Nb de formes (zones ou lignes) importées", null=True, blank=True
    )
    import_status = models.CharField(
        _("Import status"), max_length=32, choices=STATUSES, null=True
    )
    import_date = models.DateTimeField(_("Latest status date"), null=True, blank=True)
    task_id = models.CharField(
        _("Celery task id"), max_length=256, null=True, blank=True
    )
    import_error_msg = models.TextField(_("Import error message"), blank=True)
    copy_to_staging = models.BooleanField(
        _("Copy to staging?"), help_text=_("Don't touch this please"), default=False
    )

    class Meta:
        verbose_name = _("Map")
        verbose_name_plural = _("Maps")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["map_type"]),
        ]

    def __str__(self):
        return self.name


class ZoneManager(models.Manager):
    """Custom manager for Zone with spatial query helpers."""

    def find_covering(self, centroids, map_type, dept_code):
        """Find the zone covering each centroid via a single DB roundtrip.

        Uses a LATERAL JOIN so each centroid gets its own GiST index scan
        on ``ST_Covers``. Returns ``{key: Zone}`` — only matched centroids
        appear in the result.
        """
        values_parts = []
        params = []
        for key, centroid in centroids.items():
            values_parts.append(
                "(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)"
            )
            params.extend([str(key), centroid.x, centroid.y])

        values_sql = ", ".join(values_parts)
        params.extend([str(map_type), dept_code])

        sql = f"""
            WITH centroids(point_id, geom) AS (VALUES {values_sql})
            SELECT c.point_id, z.id
            FROM centroids c
            LEFT JOIN LATERAL (
                SELECT zz.id
                FROM geodata_zone zz
                JOIN geodata_map m ON zz.map_id = m.id
                WHERE m.map_type = %s
                AND m.departments @> ARRAY[%s]::varchar[]
                AND ST_Covers(zz.geometry, c.geom)
                LIMIT 1
            ) z ON TRUE
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # Collect matched zone IDs and map them back to Zone objects.
        point_to_zone_id = {}
        zone_ids = set()
        for point_id, zone_id in rows:
            if zone_id is not None:
                point_to_zone_id[point_id] = zone_id
                zone_ids.add(zone_id)

        if not zone_ids:
            return {}

        zones_by_id = self.in_bulk(zone_ids)
        return {
            point_id: zones_by_id[zone_id]
            for point_id, zone_id in point_to_zone_id.items()
        }

    def find_nearest(self, centroid, map_type, dept_code, max_distance_m):
        """Find the nearest zone of the given type within a distance cap.

        Uses ``ST_DWithin`` for spatial index filtering, then
        ``ST_Distance`` on the geography column for exact metre ordering.
        """
        return (
            self.filter(
                map__map_type=map_type,
                map__departments__contains=[dept_code],
            )
            .filter(geometry__dwithin=(centroid, D(m=max_distance_m)))
            .annotate(dist=Distance("geometry", centroid))
            .order_by("dist")
            .first()
        )


class Zone(gis_models.Model):
    """Stores an annotated geographic polygon(s)."""

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="zones")
    # `geography=True`: query with __covers/__coveredby/__intersects, NOT
    # __contains/__within/__overlaps (silent cast to geometry bypasses the
    # GIST index → seq scans).
    geometry = gis_models.MultiPolygonField(
        geography=True,
        help_text=_(
            """DO NOT EDIT! We cannot easily deactivate this edition widget,
            but if you use it, you will break Envergo.
            """
        ),
    )
    area = models.BigIntegerField(_("Area"), null=True, blank=True)
    npoints = models.BigIntegerField(_("Number of points"), null=True, blank=True)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    attributes = models.JSONField(_("Entity attributes"), null=True, blank=True)

    # Note: this values was initialy stored in an array in the `attributes` json field
    # As it turns out, it's almost impossible to get the equivalent of an `overlap`
    # lookup in a json field. So after much trial and error, I had to resolve myself
    # to store this specific field in an array instead.
    species_taxrefs = ArrayField(
        verbose_name=_("Species taxrefs"),
        null=True,
        blank=True,
        base_field=models.IntegerField(),
    )

    objects = ZoneManager()

    class Meta:
        verbose_name = _("Zone")
        verbose_name_plural = _("Zones")
        indexes = [
            models.Index(fields=["-area"]),
            models.Index(fields=["-npoints"]),
        ]


class Line(gis_models.Model):
    """Stores an annotated geographic Line(s)."""

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="lines")
    # `geography=True`: query with __covers/__coveredby/__intersects, NOT
    # __contains/__within/__overlaps (silent cast to geometry bypasses the
    # GIST index → seq scans).
    geometry = gis_models.MultiLineStringField(
        geography=True,
        help_text=_(
            """DO NOT EDIT! We cannot easily deactivate this edition widget,
            but if you use it, you will break Envergo.
            """
        ),
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    attributes = models.JSONField(_("Entity attributes"), null=True, blank=True)


class Department(models.Model):
    """Water law contact data for a departement."""

    department = models.CharField(
        _("Department"),
        max_length=3,
        choices=DEPARTMENT_CHOICES,
        unique=True,
    )
    geometry = gis_models.MultiPolygonField(null=True)

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        ordering = ["department"]

    def __str__(self):
        return self.get_department_display()

    def is_amenagement_activated(self):
        """Check if there's an active amenagement config for this department."""
        # Import here to avoid circular imports
        from envergo.moulinette.models import ConfigAmenagement

        return (
            ConfigAmenagement.objects.filter(department=self, is_activated=True)
            .valid_at(timezone.now().date())
            .exists()
        )


class CatchmentAreaTile(models.Model):
    """A raster tile with catchment area data."""

    filename = models.CharField(_("Filename"), max_length=256)
    rast = gis_models.RasterField(_("Data"), srid=2154)
    copy_to_staging = models.BooleanField(
        _("Copy to staging?"), help_text=_("Don't touch this please"), default=False
    )

    class Meta:
        verbose_name = _("Catchment area tile")
        verbose_name_plural = _("Catchment area tiles")
