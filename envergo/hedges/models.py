import operator
import uuid
<<<<<<< HEAD
from collections import defaultdict
from functools import reduce
||||||| parent of 58df3585 (List species for hedges)
=======
from functools import reduce
>>>>>>> 58df3585 (List species for hedges)

from django.contrib.postgres.fields import ArrayField
from django.db import models
<<<<<<< HEAD
from django.db.models import Q
from model_utils import Choices
||||||| parent of 58df3585 (List species for hedges)
=======
from django.db.models import Q
>>>>>>> 58df3585 (List species for hedges)
from pyproj import Geod
from shapely import LineString

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"

R = 2  # Coefficient de replantation exigée

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
    def length(self):
        """Returns the geodesic length (in meters) of the line."""

        geod = Geod(ellps="WGS84")
        length = geod.geometry_length(self.geometry)
        return length

    @property
    def is_on_pac(self):
        return self.additionalData.get("surParcellePac", False)

    @property
    def hedge_type(self):
        return self.additionalData.get("typeHaie", None)

    @property
    def proximite_mare(self):
        return self.additionalData.get("proximiteMare", None)

    @property
    def vieil_arbre(self):
        return self.additionalData.get("vieilArbre", None)

    @property
    def proximite_point_eau(self):
        return self.additionalData.get("proximitePointEau", None)

    @property
    def connexion_boisement(self):
        return self.additionalData.get("connexionBoisement", None)

    @property
    def sous_ligne_electrique(self):
        return self.additionalData.get("sousLigneElectrique", None)

<<<<<<< HEAD
    def get_species_filter(self):
        """Build the filter to get possible protected species.

        Species have requirements. For example, a "Pipistrelle commune" bat
        MAY live in an "alignement arboré" or "haie multistrate" and
        requires old trees (vieilArbre is checked).
        """
        q_hedge_type = Q(hedge_types__contains=[self.hedge_type])

        exclude = []

        if not self.proximite_mare:
            exclude.append(Q(proximite_mare=True))
        if not self.vieil_arbre:
            exclude.append(Q(vieil_arbre=True))
        if not self.proximite_point_eau:
            exclude.append(Q(proximite_point_eau=True))
        if not self.connexion_boisement:
            exclude.append(Q(connexion_boisement=True))

        q_exclude = reduce(operator.or_, exclude)
        filter = q_hedge_type & ~q_exclude
        return filter

    def get_species(self):
        """Return known species that may be related to this hedge."""

        qs = Species.objects.filter(self.get_species_filter())
        return qs

||||||| parent of 58df3585 (List species for hedges)
=======
    def get_species_filter(self):
        q_hedge_type = Q(hedge_types__contains=[self.hedge_type])

        exclude = []

        if not self.proximite_mare:
            exclude.append(Q(proximite_mare=True))
        if not self.vieil_arbre:
            exclude.append(Q(vieil_arbre=True))
        if not self.proximite_point_eau:
            exclude.append(Q(proximite_point_eau=True))
        if not self.connexion_boisement:
            exclude.append(Q(connexion_boisement=True))

        q_exclude = reduce(operator.or_, exclude)
        filter = q_hedge_type & ~q_exclude
        return filter

    def get_species(self):
        """Return known specis in this hedge."""

        qs = Species.objects.filter(self.get_species_filter())
        return qs

>>>>>>> 58df3585 (List species for hedges)

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

    def hedges(self):
        return [Hedge(**h) for h in self.data]

    def hedges_to_plant(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_PLANT]

    def length_to_plant(self):
        return round(sum(h.length for h in self.hedges_to_plant()))

    def hedges_to_remove(self):
        return [Hedge(**h) for h in self.data if h["type"] == TO_REMOVE]

    def length_to_remove(self):
        return round(sum(h.length for h in self.hedges_to_remove()))

    def hedges_to_remove_pac(self):
        return [
            h
            for h in self.hedges_to_remove()
            if h.is_on_pac and h.hedge_type != "alignement"
        ]

    def lineaire_detruit_pac(self):
        return round(sum(h.length for h in self.hedges_to_remove_pac()))

    def lineaire_detruit_pac_including_alignement(self):
        return round(sum(h.length for h in self.hedges_to_remove() if h.is_on_pac))

    def lineaire_type_4_sur_parcelle_pac(self):
        return round(
            sum(
                h.length
                for h in self.hedges_to_remove()
                if h.is_on_pac and h.hedge_type == "alignement"
            )
        )

    def is_removing_near_pond(self):
        """Return True if at least one hedge to remove is near a pond."""
        return any(h.proximite_mare for h in self.hedges_to_remove())

    def is_removing_old_tree(self):
        """Return True if at least one hedge to remove is containing old tree."""
        return any(h.vieil_arbre for h in self.hedges_to_remove())

    def minimum_length_to_plant(self):
        """Returns the minimum length of hedges to plant, considering the length of hedges to remove and the
        replantation coefficient"""
        return round(R * self.length_to_remove())

    def get_minimum_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_remove in self.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        return {
            "degradee": R * lengths_by_type["degradee"],
            "buissonnante": R * lengths_by_type["buissonnante"],
            "arbustive": R * lengths_by_type["arbustive"],
            "mixte": R * lengths_by_type["mixte"],
            "alignement": R * lengths_by_type["alignement"],
        }

    def get_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_plant in self.hedges_to_plant():
            lengths_by_type[to_plant.hedge_type] += to_plant.length

        return {
            "buissonnante": lengths_by_type["buissonnante"],
            "arbustive": lengths_by_type["arbustive"],
            "mixte": lengths_by_type["mixte"],
            "alignement": lengths_by_type["alignement"],
        }

    def get_all_species(self):
        """Return all species in the set of hedges."""

        filters = [h.get_species_filter() for h in self.hedges_to_remove()]
        union = reduce(operator.or_, filters)
        qs = Species.objects.filter(union).order_by("group", "common_name")
        return qs


HEDGE_TYPES = (
    ("degradee", "Haie dégradée ou résiduelle basse"),
    ("buissonnante", "Haie buissonnante basse"),
    ("arbustive", "Haie arbustive"),
    ("alignement", "Alignement d'arbres"),
    ("mixte", "Haie mixte"),
)

SPECIES_GROUPS = Choices(
    ("amphibiens", "Amphibiens"),
    ("chauves-souris", "Chauves-souris"),
    ("flore", "Flore"),
    ("insectes", "Insectes"),
    ("mammifères-terrestres", "Mammifères terrestres"),
    ("oiseaux", "Oiseaux"),
    ("reptile", "Reptile"),
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

    # This "group" is an ad-hoc category, not related to the official biology taxonomy
    group = models.CharField("Groupe", choices=SPECIES_GROUPS, max_length=64)
    common_name = models.CharField("Nom commun", max_length=255)
    scientific_name = models.CharField("Nom scientifique", max_length=255)
    level_of_concern = models.CharField(
        "Niveau d'enjeu", max_length=16, choices=LEVELS_OF_CONCERN
    )
    highly_sensitive = models.BooleanField("Particulièrement sensible", default=False)

    hedge_types = ArrayField(
        verbose_name="Types de haies considérés",
        base_field=models.CharField(max_length=32, choices=HEDGE_TYPES),
    )
    # Those fields are in french to match existing fields describing hedges
    proximite_mare = models.BooleanField("Mare à moins de 200 m")
    proximite_point_eau = models.BooleanField("Mare ou ruisseau à moins de 10 m")
    connexion_boisement = models.BooleanField(
        "Connectée à un boisement ou à une autre haie"
    )
    vieil_arbre = models.BooleanField(
        "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités"
    )

    class Meta:
        verbose_name = "Espèce"
        verbose_name_plural = "Espèces"

    def __str__(self):
        return f"{self.common_name} ({self.scientific_name})"
