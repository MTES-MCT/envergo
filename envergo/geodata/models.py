from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


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

    """

    commune = models.CharField(
        _("Commune INSEE code"),
        max_length=5,
        validators=[RegexValidator(regex=r"^[\d]{5}$")],
    )
    section = models.CharField(
        _("Section letter(s)"),
        max_length=2,
        validators=[RegexValidator(regex=r"^[0A-Z][A-Z]$")],
    )
    prefix = models.CharField(
        _("Prefix"), max_length=3, validators=[RegexValidator(regex=r"^[\d]{3}$")]
    )
    order = models.PositiveIntegerField(_("Order"))

    class Meta:
        verbose_name = _("Parcel")
        verbose_name_plural = _("Parcels")
        unique_together = [
            ("commune", "section", "prefix", "order"),
        ]

    def __str__(self):
        return f"{self.commune} / {self.section} / {self.prefix} / {self.order:04}"
