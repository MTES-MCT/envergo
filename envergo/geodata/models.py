from django.contrib.gis.db import models as gis_models
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices


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


class Map(models.Model):
    """Holds a shapefile map."""

    name = models.CharField(_("Name"), max_length=256)
    file = models.FileField(_("File"), upload_to="maps/")
    data_type = models.CharField(_("Data type"), max_length=50, choices=MAP_TYPES)
    description = models.TextField(_("Description"))
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Map")
        verbose_name_plural = _("Maps")

    def __str__(self):
        return self.name

    def extract(self):
        from envergo.geodata.utils import extract_shapefile

        extract_shapefile(self, self.file)


class Zone(gis_models.Model):
    """Stores an annotated geographic polygon(s)."""

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="zones")
    geometry = gis_models.MultiPolygonField()

    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Zone")
        verbose_name_plural = _("Zones")
