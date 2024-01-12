import glob
import logging
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, RegexValidator
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


class Parcel(models.Model):
    """A single parcel from the french cadastre.

    This is the most granular element of land ownership in France.

    A parcel should be geographically equivalent of a single polygon
    (but we can't guarantee there are no exceptions, of course).

    A parcel identifier is made of several fields:

     - commune:
       5 char long number
       The commune's INSEE (Code Officiel Géographique) code where it's
       located (e.g 34333) THIS IS NOT THE POSTCODE!
       There are exeptions where the commune code is replaced with a district
       (« arrondissement ») code.

     - section:
       1 or two letters
       A geographical subset of the commune, identified by one or several letters.

     - prefix or "feuille":
       3 char long number
       In some cases the section can be subdivided into "feuilles" identified by
       a number. By default, « 000 ».

     - id:
       A number > 0 and <= 9999
       The actual parcel identifier inside the "feuille"

    Prefix explanation:
    By default, a section has only one "feuille" : « 000 ».
    Sometimes, a section needs to be subdivided, mainly when communes are merged.

    Example:
    The commune of Évry (code 91228) absorbed the commune of Courcouronnes (91182)
    and was renamed « Évry-Courcouronnes » but kept the code 91228.
    Courcouronne's « AA » section became a new prefix in Évry's « AA » section.

    Also, more often than not, the section and prefix are displayed as a single
    « section » field.

    So the parcel :
    911182 / AA / 000 / 1
    Became :
    91228 / AA / 182 / 1

    Fun fact, even though the "feuille" is a subdivision of the section, it is
    generally written before it (so, a prefix) in parcel identifiers.

    E.g For the IGN and betagouv apis, the parcel « 911182 / AA / 000 / 1 »
    is identified by: « 911182000AA0001 »

    """

    commune = models.CharField(
        _("Commune INSEE code"),
        max_length=5,
        validators=[
            RegexValidator(
                regex=r"^[\d]{5}$", message=_("The code must be a 5-digit number")
            )
        ],
    )
    section = models.CharField(
        _("Section letter(s)"),
        max_length=2,
        validators=[
            RegexValidator(
                regex=r"^[0A-Z][A-Z]$",
                message=_(
                    "The section must be one (zero-prefixed) or two uppercase letters."
                ),
            )
        ],
    )
    prefix = models.CharField(
        _("Prefix"),
        max_length=3,
        validators=[
            RegexValidator(
                regex=r"^[\d]{3}$", message=_("The prefix must be a 3-digit number.")
            )
        ],
    )
    order = models.PositiveIntegerField(
        _("Order"),
        validators=[
            MaxValueValidator(
                limit_value=9999,
                message=_("The parcel must be a number between 1 and 9999"),
            )
        ],
    )

    class Meta:
        verbose_name = _("Parcel")
        verbose_name_plural = _("Parcels")

    def __str__(self):
        return f"{self.commune} / {self.section} / {self.prefix} / {self.order:04}"

    @property
    def reference(self):
        """Return the reference, as noted by the IGN or Etalab apis.

        Those kind of references are used, for example for IGN's geocoder
        service:
        https://geoservices.ign.fr/documentation/services/services-beta/geocodage-beta/documentation-du-geocodage#2463

        Or in Etalab's cadastre data:
        https://cadastre.data.gouv.fr/datasets/cadastre-etalab
        """
        return f"{self.commune}{self.prefix}{self.section}{self.order:04}"


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
    geometry = gis_models.MultiPolygonField()

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        ordering = ["department"]

    def __str__(self):
        return self.get_department_display()
