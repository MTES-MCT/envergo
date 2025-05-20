import operator
import uuid
from functools import reduce

from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone
from model_utils import Choices
from pyproj import Geod
from shapely import LineString, centroid, union_all

from envergo.geodata.models import Zone
from envergo.geodata.utils import (
    compute_hedge_density_around_point,
    get_department_from_coords,
)

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"

R = 1.5  # Coefficient de replantation exigée

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857

EPSG_LAMB93 = 2154


class Hedge:
    """Represent a single hedge."""

    def __init__(self, id, latLngs, type, additionalData=None):
        self.id = id  # The edge reference, e.g A1, A2…
        self.latLngs = latLngs
        self.geometry = LineString(
            [(latLng["lng"], latLng["lat"]) for latLng in latLngs]
        )
        self.type = type
        self.additionalData = additionalData or {}

    def toDict(self):
        """Export hedge data back as a dict.

        This is only useful for tests."""
        return {
            "id": self.id,
            "type": self.type,
            "additionalData": self.additionalData,
            "latLngs": self.latLngs,
        }

    @property
    def geos_geometry(self):
        geom = GEOSGeometry(self.geometry.wkt, srid=EPSG_WGS84)
        return geom

    @property
    def length(self):
        """Returns the geodesic length (in meters) of the line."""

        geod = Geod(ellps="WGS84")
        length = geod.geometry_length(self.geometry)
        return length

    def has_property(self, property_name):
        """Check if the hedge has a specific property."""
        return property_name in self.additionalData

    def prop(self, property_name):
        """Get the value of a specific property."""
        return self.additionalData.get(property_name, None)

    @property
    def is_on_pac(self):
        return self.additionalData.get("sur_parcelle_pac", False)

    @property
    def hedge_type(self):
        return self.additionalData.get("type_haie", None)

    @property
    def mode_destruction(self):
        return self.additionalData.get("mode_destruction", None)

    @property
    def position(self):
        return self.additionalData.get("position", None)

    @property
    def proximite_mare(self):
        return self.additionalData.get("proximite_mare", None)

    @property
    def vieil_arbre(self):
        return self.additionalData.get("vieil_arbre", None)

    @property
    def proximite_point_eau(self):
        return self.additionalData.get("proximite_point_eau", None)

    @property
    def connexion_boisement(self):
        return self.additionalData.get("connexion_boisement", None)

    @property
    def sous_ligne_electrique(self):
        return self.additionalData.get("sous_ligne_electrique", None)

    def get_species_filter(self):
        """Build the filter to get possible protected species.

        Species have requirements. For example, a "Pipistrelle commune" bat
        MAY live in an "alignement arboré" or "haie multistrate" and
        requires old trees (vieil_arbre is checked).
        """
        q_hedge_type = Q(species_maps__hedge_types__contains=[self.hedge_type])

        properties_to_exclude = []
        for p, _ in HEDGE_PROPERTIES:
            if p in self.additionalData and not self.additionalData[p]:
                properties_to_exclude.append(p)

        filter = q_hedge_type
        if properties_to_exclude:
            q_exclude = Q(species_maps__hedge_properties__overlap=properties_to_exclude)
            filter &= ~q_exclude

        return filter

    def get_species(self):
        """Return known species that may be related to this hedge."""

        zone_subquery = Zone.objects.filter(
            Q(geometry__intersects=self.geos_geometry)
        ).filter(Q(map_id=OuterRef("map_id")))

        qs = (
            Species.objects.annotate(map_id=F("species_maps__map_id"))
            .filter(self.get_species_filter())
            .filter(Exists(zone_subquery))
        )
        return qs


class HedgeData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    class Meta:
        verbose_name = "Hedge data"
        verbose_name_plural = "Hedge data"

    def __str__(self):
        return str(self.id)

    def __iter__(self):
        return iter(self.hedges())

    def get_bounding_box(self, hedges):
        """Return the bounding box of the given hedge set."""

        min_x, min_y, max_x, max_y = hedges[0].geometry.bounds
        for hedge in hedges[1:]:
            x0, y0, x1, y1 = hedge.geometry.bounds
            min_x = min(min_x, x0)
            min_y = min(min_y, y0)
            max_x = max(max_x, x1)
            max_y = max(max_y, y1)
        box = Polygon.from_bbox([min_x, min_y, max_x, max_y])
        return box

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

    def hedges_to_remove_pac(self):
        return [
            h
            for h in self.hedges_to_remove()
            if h.is_on_pac and h.hedge_type != "alignement"
        ]

    def get_centroid_to_remove(self):
        hedges_to_remove_geometries = [h.geometry for h in self.hedges_to_remove()]
        hedges_centroid = centroid(union_all(hedges_to_remove_geometries))
        return hedges_centroid

    def get_department(self):
        hedges_centroid = self.get_centroid_to_remove()
        code_department = get_department_from_coords(
            hedges_centroid.x, hedges_centroid.y
        )
        return code_department

    def hedges_to_plant_pac(self):
        def pac_selection(h):
            """Check if hedge must be taken into account for pac plantation."""
            res = h.is_on_pac and h.hedge_type != "alignement"
            if h.has_property("mode_plantation"):
                res = res and h.prop("mode_plantation") == "plantation"
            return res

        return [h for h in self.hedges_to_plant() if pac_selection(h)]

    def length_to_plant_pac(self):
        return sum(h.length for h in self.hedges_to_plant_pac())

    def lineaire_detruit_pac(self):
        return sum(h.length for h in self.hedges_to_remove_pac())

    def lineaire_detruit_pac_including_alignement(self):
        return sum(h.length for h in self.hedges_to_remove() if h.is_on_pac)

    def lineaire_type_4_sur_parcelle_pac(self):
        return sum(
            h.length
            for h in self.hedges_to_remove()
            if h.is_on_pac and h.hedge_type == "alignement"
        )

    def is_removing_near_pond(self):
        """Return True if at least one hedge to remove is near a pond."""
        return any(h.proximite_mare for h in self.hedges_to_remove())

    def is_removing_old_tree(self):
        """Return True if at least one hedge to remove is containing old tree."""
        return any(h.vieil_arbre for h in self.hedges_to_remove())

    def get_all_species(self):
        """Return the local list of protected species."""

        zone_subquery = (
            Zone.objects.filter(
                Q(geometry__intersects=self.get_bounding_box(self.hedges()))
            )
            .filter(map__map_type="species")
            .filter(Q(map_id=OuterRef("map_id")))
            .filter(species_taxrefs__overlap=OuterRef("taxref_ids"))
        )

        filters = [h.get_species_filter() for h in self.hedges_to_remove()]
        union = reduce(operator.or_, filters)
        species = (
            Species.objects.filter(union)
            .annotate(map_id=F("species_maps__map_id"))
            .order_by("group", "common_name")
            .filter(Exists(zone_subquery))
        )
        return species

    def compute_density_with_artifacts(self):
        """Compute the density of hedges around the hedges to remove at 200m and 5000m."""

        # get two circles at 200m and 5000m from the centroid of the hedges to remove
        centroid_shapely = self.get_centroid_to_remove()
        centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)

        density_200 = compute_hedge_density_around_point(centroid_geos, 200)
        density_5000 = compute_hedge_density_around_point(centroid_geos, 5000)

        return density_200, density_5000, centroid_geos

    def compute_density(self):
        """Compute the density of hedges around the hedges to remove at 200m and 5000m."""
        density_200, density_5000, _ = self.compute_density_with_artifacts()
        self.density = {
            "length_200": density_200["artifacts"]["length"],
            "length_5000": density_5000["artifacts"]["length"],
            "area_200_ha": density_200["artifacts"]["area_ha"],
            "area_5000_ha": density_5000["artifacts"]["area_ha"],
            "density_200": density_200["density"],
            "density_5000": density_5000["density"],
        }


HEDGE_TYPES = (
    ("degradee", "Haie dégradée ou résiduelle basse"),
    ("buissonnante", "Haie buissonnante basse"),
    ("arbustive", "Haie arbustive"),
    ("alignement", "Alignement d'arbres"),
    ("mixte", "Haie mixte"),
)

HEDGE_PROPERTIES = (
    ("proximite_mare", "Mare à moins de 200 m"),
    ("proximite_point_eau", "Mare ou ruisseau à moins de 10 m"),
    ("connexion_boisement", "Connectée à un boisement ou à une autre haie"),
    ("vieil_arbre", "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités"),
)

SPECIES_GROUPS = Choices(
    ("amphibiens", "Amphibiens"),
    ("chauves-souris", "Chauves-souris"),
    ("flore", "Flore"),
    ("insectes", "Insectes"),
    ("mammiferes-terrestres", "Mammifères terrestres"),
    ("oiseaux", "Oiseaux"),
    ("reptiles", "Reptiles"),
)

KINGDOMS = Choices(
    ("animalia", "Animalia"),
    ("archaea", "Archaea"),
    ("bacteria", "Bacteria"),
    ("chromista", "Chromista"),
    ("fungi", "Fungi"),
    ("plantae", "Plantae"),
    ("protozoa", "Protozoa"),
)

LEVELS_OF_CONCERN = Choices(
    ("faible", "Faible"),
    ("moyen", "Moyen"),
    ("fort", "Fort"),
    ("tres_fort", "Très fort"),
    ("majeur", "Majeur"),
)


class Species(models.Model):
    """Represent a single species."""

    # This is the unique species identifier (cd_nom) in the INPN TaxRef database
    # https://inpn.mnhn.fr/telechargement/referentielEspece/referentielTaxo
    # The reason why this is an array is because sometimes, there are duplicates
    # (e.g) a species has been describe by several naturalists over the years before
    # they realized it was a duplicate.
    # Hence, for a given scientific name, there can be several TaxRef ids.
    taxref_ids = ArrayField(
        null=True, verbose_name="Ids TaxRef (cd_nom)", base_field=models.IntegerField()
    )

    # This "group" is an ad-hoc category, not related to the official biology taxonomy
    group = models.CharField("Groupe", choices=SPECIES_GROUPS, max_length=64)

    kingdom = models.CharField("Règne", choices=KINGDOMS, max_length=32, blank=True)
    common_name = models.CharField("Nom commun", max_length=255)
    scientific_name = models.CharField("Nom scientifique", max_length=255, unique=True)
    level_of_concern = models.CharField(
        "Niveau d'enjeu", max_length=16, choices=LEVELS_OF_CONCERN
    )
    highly_sensitive = models.BooleanField("Particulièrement sensible", default=False)

    class Meta:
        verbose_name = "Espèce"
        verbose_name_plural = "Espèces"

    def __str__(self):
        return f"{self.common_name} ({self.scientific_name})"


class SpeciesMap(models.Model):
    """Represent a single species map."""

    species = models.ForeignKey(
        Species,
        related_name="species_maps",
        on_delete=models.CASCADE,
        verbose_name="Espèce",
    )
    map = models.ForeignKey(
        "geodata.Map",
        related_name="species_maps",
        on_delete=models.CASCADE,
        verbose_name="Carte",
    )
    species_map_file = models.ForeignKey(
        "SpeciesMapFile",
        verbose_name="Importé par",
        related_name="species_maps",
        null=True,
        on_delete=models.CASCADE,
    )

    hedge_types = ArrayField(
        verbose_name="Types de haies considérés",
        base_field=models.CharField(max_length=32, choices=HEDGE_TYPES),
    )
    hedge_properties = ArrayField(
        verbose_name="Propriétés de la haie",
        help_text="Propriétés requises par l'espèce",
        base_field=models.CharField(max_length=32, choices=HEDGE_PROPERTIES),
    )

    class Meta:
        verbose_name = "Carte d'espèce"
        verbose_name_plural = "Cartes d'espèces"
        unique_together = ("species", "map")


IMPORT_STATUSES = Choices(
    ("success", "Succès"),
    ("partial_success", "Succès partiel"),
    ("failure", "Échec"),
)


class SpeciesMapFile(models.Model):
    """Holds a csv file that links species and their caracteristics to a map."""

    name = models.CharField("Nom", max_length=255, help_text="Nom pense-bête")
    file = models.FileField("Fichier", upload_to="species_maps/")
    map = models.ForeignKey(
        "geodata.Map", on_delete=models.PROTECT, verbose_name="Carte"
    )

    created_at = models.DateTimeField("Créé le", default=timezone.now)
    import_status = models.CharField(
        "Statut d'import", max_length=32, choices=IMPORT_STATUSES, null=True
    )
    import_date = models.DateTimeField("Date du dernier import", null=True, blank=True)
    task_id = models.CharField("Celery task id", max_length=256, null=True, blank=True)
    import_log = models.TextField("Log d'import", blank=True)

    class Meta:
        verbose_name = "Fichier de carte d'espèces"
        verbose_name_plural = "Fichiers de carte d'espèces"

    def __str__(self):
        return self.file.name
