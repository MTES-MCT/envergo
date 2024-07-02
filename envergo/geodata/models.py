import glob
import logging
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.db import models
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
    """Holds a shapefile map."""

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
    geometry = gis_models.MultiPolygonField(
        _("Simplified geometry"),
        help_text=_(
            """DO NOT EDIT! We cannot easily deactivate this edition widget,
            but if you use it, you will break EnvErgo.
            """
        ),
        geography=True,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    expected_zones = models.IntegerField(_("Expected zones"), default=0)
    imported_zones = models.IntegerField(_("Imported zones"), null=True, blank=True)
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

    def __str__(self):
        return self.name

    @contextmanager
    def extract_shapefile(self):
        with TemporaryDirectory() as tmpdir:
            logger.info("Extracting map zip file")
            zf = zipfile.ZipFile(self.file)
            zf.extractall(tmpdir)

            logger.info("Find .shp file path")
            paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !
            shapefile = paths[0]
            yield shapefile


class Zone(gis_models.Model):
    """Stores an annotated geographic polygon(s)."""

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="zones")
    geometry = gis_models.MultiPolygonField(
        geography=True,
        help_text=_(
            """DO NOT EDIT! We cannot easily deactivate this edition widget,
            but if you use it, you will break EnvErgo.
            """
        ),
    )
    area = models.BigIntegerField(_("Area"), null=True, blank=True)
    npoints = models.BigIntegerField(_("Number of points"), null=True, blank=True)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Zone")
        verbose_name_plural = _("Zones")
        indexes = [
            models.Index(fields=["-area"]),
            models.Index(fields=["-npoints"]),
        ]


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

    def is_activated(self):
        config = getattr(self, "moulinette_config", None)
        return config and config.is_activated


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
