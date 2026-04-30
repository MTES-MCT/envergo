import operator
import uuid
from functools import reduce
from typing import Self

import shapely
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiLineString, Polygon
from django.contrib.gis.measure import D
from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.utils import timezone
from model_utils import Choices
from pyproj import Geod, Transformer
from shapely import LineString, centroid, union_all

from envergo.geodata.models import Department, Zone
from envergo.geodata.utils import (
    compute_hedge_densities_around_point,
    compute_hedge_density_around_lines,
    get_department_from_coords,
)

TO_PLANT = "TO_PLANT"
TO_REMOVE = "TO_REMOVE"


class HedgeTypeBase(models.TextChoices):
    """This enum should list all the existing type. But it should not be used directly.

    Prefer using HedgeTypeFactory.build_from_context."""

    DEGRADEE = "degradee", "Haie dégradée ou résiduelle basse"
    BUISSONNANTE = "buissonnante", "Haie buissonnante basse"
    ARBUSTIVE = "arbustive", "Haie arbustive"
    MIXTE = "mixte", "Haie mixte"
    ALIGNEMENT = "alignement", "Alignement d'arbres"


class HedgeTypeFactory(models.TextChoices):
    """Use this factory to build the hedge types enum depending on the context of your simulation"""

    @classmethod
    def build_from_context(cls, single_procedure: bool):

        single_procedure_label_map = {
            HedgeTypeBase.MIXTE: "Haie arborée",
        }

        choices = HedgeTypeBase.choices
        if single_procedure:
            choices = [
                (key, single_procedure_label_map.get(key, label))
                for key, label in HedgeTypeBase.choices
                if key != HedgeTypeBase.DEGRADEE
            ]

        hedge_type = models.TextChoices(
            "ContextualHedgeType",
            {key.upper(): (key, label) for key, label in choices},
            type=HedgeTypeFactory,
        )
        hedge_type.faq_url = settings.HAIE_FAQ_URLS[
            "RU_HEDGES_TYPES" if single_procedure else "DC_HEDGES_TYPES"
        ]
        return hedge_type


HEDGE_PROPERTIES = (
    ("proximite_mare", "Mare à moins de 200 m"),
    ("ripisylve", "En bordure de cours d'eau ou de plan d'eau (haie ripisylve)"),
    ("connexion_boisement", "Connectée à un boisement ou à une autre haie"),
    ("vieil_arbre", "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités"),
)

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
    def geometry_lamb93(self):
        """Return a shapely geometry with a Lambert 93 projection."""

        transformer = Transformer.from_crs(EPSG_WGS84, EPSG_LAMB93, always_xy=True)
        lamb93 = shapely.transform(
            self.geometry, transformer.transform, interleaved=False
        )
        return lamb93

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
    def mode_plantation(self):
        return self.additionalData.get("mode_plantation", None)

    @property
    def proximite_mare(self):
        return self.additionalData.get("proximite_mare", None)

    @property
    def vieil_arbre(self):
        return self.additionalData.get("vieil_arbre", None)

    @property
    def ripisylve(self):
        return self.additionalData.get("ripisylve", None)

    @property
    def connexion_boisement(self):
        return self.additionalData.get("connexion_boisement", None)

    @property
    def sous_ligne_electrique(self):
        return self.additionalData.get("sous_ligne_electrique", None)

    @property
    def effective_hedge_type(self):
        """Return the hedge type to use for species filtering.

        Recently planted hedges are treated as degraded from a biodiversity
        standpoint, regardless of their declared type.
        """
        if self.prop("recemment_plantee"):
            return HedgeTypeBase.DEGRADEE
        return self.hedge_type

    @property
    def missing_ecological_properties(self):
        """Return hedge properties that are explicitly absent.

        Species requiring any of these properties will be excluded from the
        cortège, since the hedge does not satisfy the ecological condition.
        """
        return [
            p
            for p, _ in HEDGE_PROPERTIES
            if p in self.additionalData and not self.additionalData[p]
        ]


class HedgeList(list[Hedge]):
    """A class representing a list of Hedge objects.

    This class is a basic list with some filtering api added, and a chainable api.

    For example, for selecting the hedges to remove of type "haie mixte" with a
    "vieilArbre" property:

    hedges = HedgeList(hedges).to_remove().mixte().prop("vieilArbre")
    """

    def __init__(self, *args, label=None, **kwargs):
        self.label = label
        super().__init__(*args, **kwargs)

    @property
    def names(self):
        return ", ".join(h.id for h in self)

    @property
    def length(self):
        return sum(h.length for h in self)

    def to_plant(self) -> Self:
        return HedgeList([h for h in self if h.type == TO_PLANT])

    def to_remove(self) -> Self:
        return HedgeList([h for h in self if h.type == TO_REMOVE])

    def pac(self) -> Self:
        return HedgeList(
            [
                h
                for h in self
                if h.is_on_pac and h.hedge_type != HedgeTypeBase.ALIGNEMENT
            ]
        )

    def mixte(self) -> Self:
        return HedgeList([h for h in self if h.hedge_type == HedgeTypeBase.MIXTE])

    def arbustive(self) -> Self:
        return HedgeList([h for h in self if h.hedge_type == HedgeTypeBase.ARBUSTIVE])

    def buissonnante(self) -> Self:
        return HedgeList(
            [h for h in self if h.hedge_type == HedgeTypeBase.BUISSONNANTE]
        )

    def degradee(self) -> Self:
        return HedgeList([h for h in self if h.hedge_type == HedgeTypeBase.DEGRADEE])

    def alignement(self) -> Self:
        return HedgeList([h for h in self if h.hedge_type == HedgeTypeBase.ALIGNEMENT])

    def n_alignement(self) -> Self:
        """Select all hedges that are of ALL types BUT alignement.

        Useful because we often need to separate "haies" from "alignements d'arbres".
        """
        return HedgeList([h for h in self if h.hedge_type != HedgeTypeBase.ALIGNEMENT])

    def ru(self) -> Self:
        """Select all hedges that are covered by the single procedure (régime unique, RU)."""
        return (
            self.n_alignement()
            .prop("!bord_batiment")
            .prop("!parc_jardin")
            .prop("!place_publique")
        )

    def l350_3(self) -> Self:
        """Select all tree alignment that are covered the L350-3 regulation."""
        return self.alignement().prop("bord_voie")

    def hru(self) -> Self:
        """Select all hedges are not covered by either the single procedure or L350-3"""
        ru = self.ru()
        l350_3 = self.l350_3()
        return HedgeList([h for h in self if h not in ru and h not in l350_3])

    def to_multilinestring(self):
        """Return a MultiLineString combining all hedges in this list."""
        return MultiLineString([h.geos_geometry for h in self], srid=EPSG_WGS84)

    def filter(self, f) -> Self:
        """Filter the hedge list using a specific filtering method."""
        return HedgeList([h for h in self if f(h)])

    def type(self, t) -> Self:
        """Filter hedges by hedge type. Prefix with a "!" to negate the filter."""

        # Make sure the type filter is valid
        if t.replace("!", "") not in HedgeTypeBase.values:
            raise ValueError(f"Argument hedge_type must be in {HedgeTypeBase}")

        if t.startswith("!"):
            hedges = HedgeList([h for h in self if h.hedge_type != t.replace("!", "")])
        else:
            hedges = HedgeList([h for h in self if h.hedge_type == t])
        return hedges

    def prop(self, p) -> Self:
        """Select hedges with a given prod. Prefix with "!" to negate the filter.

        IMPORTANT! We don't filter out the hedges that DO NOT feature the property.
        """

        if p.startswith("!"):
            p = p.replace("!", "")
            hedges = HedgeList(
                [h for h in self if not h.prop(p) or not h.has_property(p)]
            )
        else:
            hedges = HedgeList([h for h in self if h.prop(p) or not h.has_property(p)])
        return hedges


class HedgeData(models.Model):
    """Hedge data model.
    Field data is a json listing hedges"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()
    _density = models.JSONField(null=True, default=None)
    _length_to_remove = models.FloatField(
        verbose_name="Longueur détruite", null=True, default=None
    )
    _length_to_plant = models.FloatField(
        verbose_name="Longueur plantée", null=True, default=None
    )

    class Meta:
        verbose_name = "Hedge data"
        verbose_name_plural = "Hedge data"

    def __str__(self):
        return str(self.id)

    def __iter__(self):
        return iter(self.hedges())

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "data" in update_fields:
            # recompute cached value
            self._length_to_remove = None
            self._length_to_plant = None
            self._length_to_remove = self.length_to_remove()
            self._length_to_plant = self.length_to_plant()

            if update_fields is not None:
                kwargs["update_fields"] = list(
                    set(update_fields) | {"_length_to_remove", "_length_to_plant"}
                )
        super().save(*args, **kwargs)

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
        return HedgeList([Hedge(**h) for h in self.data])

    def hedges_to_plant(self):
        return self.hedges().to_plant()

    def length_to_plant(self):
        if self._length_to_plant is None:
            self._length_to_plant = self.hedges().to_plant().length
        return self._length_to_plant

    def hedges_to_remove(self):
        return self.hedges().to_remove()

    def length_to_remove(self):
        if self._length_to_remove is None:
            self._length_to_remove = self.hedges().to_remove().length
        return self._length_to_remove

    def hedges_to_remove_pac(self):
        return self.hedges().to_remove().pac()

    def hedges_to_plant_pac(self):
        def pac_selection(h):
            """Check if hedge must be taken into account for pac plantation."""
            res = h.is_on_pac and h.hedge_type != "alignement"
            if h.has_property("mode_plantation"):
                res = res and h.prop("mode_plantation") == "plantation"
            return res

        return HedgeList([h for h in self.hedges_to_plant() if pac_selection(h)])

    def length_to_plant_pac(self):
        return self.hedges_to_plant_pac().length

    def lineaire_detruit_pac(self):
        return self.hedges_to_remove_pac().length

    def lineaire_detruit_pac_including_alignement(self):
        return sum(h.length for h in self.hedges_to_remove() if h.is_on_pac)

    def lineaire_type_4_sur_parcelle_pac(self):
        return sum(
            h.length
            for h in self.hedges_to_remove()
            if h.is_on_pac and h.hedge_type == "alignement"
        )

    def get_centroid_to_remove(self):
        """Returns hedges to remove centroid"""
        hedges_to_remove_geometries = [h.geometry for h in self.hedges_to_remove()]
        hedges_centroid = centroid(union_all(hedges_to_remove_geometries))
        return hedges_centroid

    def get_department(self):
        hedges_centroid = self.get_centroid_to_remove()
        code_department = get_department_from_coords(
            hedges_centroid.x, hedges_centroid.y
        )
        return code_department

    def hedges_filter(self, hedge_to, hedge_type, *props) -> HedgeList:
        """HedgeData filter

        Args:
            hedge_to: TO_PLANT or TO_REMOVE
            hedge_type: hedge type from HedgeType
            props: other hedge properties

        Returns:
            HedgeList: hedges list filtered

        Raises:
            ValueError: If hedge to or type argument has a wrong value
        """

        if hedge_to not in (TO_REMOVE, TO_PLANT):
            raise ValueError(f"Argument hedge_to must ben in {TO_REMOVE} or {TO_PLANT}")

        hedges = self.hedges()

        if hedge_to == TO_REMOVE:
            hedges = hedges.to_remove()
        elif hedge_to == TO_PLANT:
            hedges = hedges.to_plant()

        hedges = hedges.type(hedge_type)

        for prop in props:
            hedges = hedges.prop(prop)

        return hedges

    def is_removing_near_pond(self):
        """Return True if at least one hedge to remove is near a pond."""
        return any(h.proximite_mare for h in self.hedges_to_remove())

    def is_removing_old_tree(self):
        """Return True if at least one hedge to remove is containing old tree."""
        return any(h.vieil_arbre for h in self.hedges_to_remove())

    def get_all_species_hru(self):
        """Return the local list of protected species (legacy HRU logic)."""
        return Species.hru.for_hedges(self.hedges_to_remove())

    def get_all_species(self):
        """Return the RU list of protected species."""
        return Species.ru.for_hedges(self.hedges_to_remove())

    def compute_density_around_points_with_artifacts(self):
        """Compute the density of hedges around the hedges to remove at 200m and 5000m."""

        centroid_shapely = self.get_centroid_to_remove()
        centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)
        bundle = compute_hedge_densities_around_point(centroid_geos, radii=[200, 5000])

        return bundle[200], bundle[5000], centroid_geos

    def compute_density_around_lines_with_artifacts(self):
        """Compute the density of hedges around the hedges to remove in 400m buffer."""

        hedges_geom = self.hedges_to_remove().to_multilinestring()
        return compute_hedge_density_around_lines(hedges_geom, 400)

    @property
    def density_around_centroid(self):
        """Lazily compute and cache centroid-based density (200m + 5000m circles)."""

        if not self._density or "around_centroid" not in self._density:
            density_200, density_5000, _ = (
                self.compute_density_around_points_with_artifacts()
            )
            if not self._density:
                self._density = {}
            self._density["around_centroid"] = {
                "length_200": density_200["artifacts"]["length"],
                "length_5000": density_5000["artifacts"]["length"],
                "area_200_ha": density_200["artifacts"]["area_ha"],
                "area_5000_ha": density_5000["artifacts"]["area_ha"],
                "density_200": density_200["density"],
                "density_5000": density_5000["density"],
            }
            self.save()
        return self._density["around_centroid"]

    @property
    def density_around_lines(self):
        """Lazily compute and cache line-buffer density (400m buffer)."""

        if not self._density or "around_lines" not in self._density:
            density_400_buffer = self.compute_density_around_lines_with_artifacts()
            if not self._density:
                self._density = {}
            self._density["around_lines"] = {
                "length_400": density_400_buffer["artifacts"]["length"],
                "area_400_ha": density_400_buffer["artifacts"]["area_ha"],
                "density_400": density_400_buffer["density"],
            }
            self.save()
        return self._density["around_lines"]

    @property
    def density(self):
        """Legacy method, deprecated."""

        raise AttributeError(
            "Use density_around_centroid or density_around_lines instead of density."
        )

    def has_hedges_outside_department(self, department: Department):
        """
        Check if any hedge in the HedgeData instance is outside the given department geometry.

        Args:
            department: The department model with its geometry prefetched.

        Returns:
            bool: True if there are hedges outside the department geometry, False otherwise.
        """
        if not department:
            return True
        department_geom = GEOSGeometry(department.geometry.wkt)
        for hedge in self.hedges():
            if not department_geom.intersects(hedge.geos_geometry):
                return True
        return False

    def get_statistics(self):
        hedge_centroid_coords = self.get_centroid_to_remove()
        ru_to_plant = self.hedges_to_plant().ru()
        l350_3_to_plant = self.hedges_to_plant().l350_3()
        hru_to_plant = self.hedges_to_plant().hru()
        ru_to_remove = self.hedges_to_remove().ru()
        l350_3_to_remove = self.hedges_to_remove().l350_3()
        hru_to_remove = self.hedges_to_remove().hru()
        return {
            "longueur_detruite": round(self.length_to_remove(), 1),
            "longueur_plantee": round(self.length_to_plant(), 1),
            "nb_traces_d_categ": {
                "ru": len(ru_to_remove),
                "l350-3": len(l350_3_to_remove),
                "hru": len(hru_to_remove),
            },
            "nb_traces_p_categ": {
                "ru": len(ru_to_plant),
                "l350-3": len(l350_3_to_plant),
                "hru": len(hru_to_plant),
            },
            "longueur_d_categ": {
                "ru": round(ru_to_remove.length, 1),
                "l350-3": round(l350_3_to_remove.length, 1),
                "hru": round(hru_to_remove.length, 1),
            },
            "longueur_p_categ": {
                "ru": round(ru_to_plant.length, 1),
                "l350-3": round(l350_3_to_plant.length, 1),
                "hru": round(hru_to_plant.length, 1),
            },
            "lnglat_centroide_haie_detruite": (
                f"{hedge_centroid_coords.x}, {hedge_centroid_coords.y}"
            ),
            "dept_haie_detruite": self.get_department(),
        }


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
    ("non_documente", "Non documenté"),
    ("faible", "Faible"),
    ("moyen", "Moyen"),
    ("fort", "Fort"),
    ("tres_fort", "Très fort"),
    ("majeur", "Majeur"),
)


class HruSpeciesQuerySet(models.QuerySet):
    """Species queryset for the HRU (droit constant) pipeline.

    species must be confirmed in zones that directly intersect the hedge,
    AND their cd_noms must overlap the zone's species_taxrefs array.
    """

    def for_hedges(self, hedges):
        """Return species confirmed in zones intersecting the given hedges."""

        hedges = HedgeList(hedges)
        filters = [self.build_filter(h) for h in hedges]
        if not filters:
            return self.none()

        union = reduce(operator.or_, filters)
        return self.filter(union).distinct().order_by("group", "common_name")

    def build_filter(self, hedge):
        """Build a Q filter for species confirmed in zones intersecting a hedge.

        HRU is observation-based: species are only included when both their
        geographic zone intersects the hedge AND their cd_noms appear in
        the zone's species_taxrefs array (confirming local observation).
        """
        q_filter = Q(habitats__hedge_types__contains=[hedge.effective_hedge_type])

        if hedge.missing_ecological_properties:
            q_filter &= ~Q(
                habitats__hedge_properties__overlap=hedge.missing_ecological_properties
            )

        zone_subquery = (
            Zone.objects.filter(geometry__intersects=hedge.geos_geometry)
            .filter(map_id=OuterRef("habitats__map_id"))
            .filter(species_taxrefs__overlap=OuterRef("cd_noms"))
        )
        q_filter &= Q(Exists(zone_subquery))
        return q_filter


SPECIES_BUFFER_DISTANCE = D(m=400)


def group_hedges_by_signature(hedges):
    """Group hedges by their (hedge_type, missing_properties) filter signature.

    Hedges sharing the same signature produce identical SpeciesHabitat filters,
    so they can be treated as a single geographic group for zone proximity.
    """
    groups = {}
    for h in hedges:
        sig = (h.effective_hedge_type, tuple(sorted(h.missing_ecological_properties)))
        groups.setdefault(sig, []).append(h)
    return groups

# Numeric ranks for sorting species by level_of_concern in the RU pipeline.
# Derived from LEVELS_OF_CONCERN ordering (1 = lowest, 6 = highest).
LEVEL_OF_CONCERN_ORDER = {
    value: rank for rank, (value, _) in enumerate(LEVELS_OF_CONCERN, 1)
}

LEVEL_OF_CONCERN_WHENS = [
    When(level_of_concern=value, then=Value(rank))
    for value, rank in LEVEL_OF_CONCERN_ORDER.items()
]


class RuSpeciesQuerySet(models.QuerySet):
    """Species queryset for the RU (régime unique) pipeline.

    All species from SpeciesHabitats within 400m are considered potentially present.
    Highly sensitive species not observed locally (cd_ref absent from nearby
    zone.species_taxrefs) are excluded entirely.

    The zone data (nearby map ids and observed cd_refs) is prefetched in
    a single query, then injected as plain Python values into the species
    filter and annotations. This avoids per-hedge correlated subqueries
    whose cost scales linearly with hedge count.
    """

    def for_hedges(self, hedges):
        """Return species potentially near the given hedges.

        Annotated with local_level_of_concern, observed_locally, and
        level_order. Sorted by level of concern descending, then by name.
        """
        hedges = HedgeList(hedges)
        if not hedges:
            return self.none()

        signature_map_ids, observed_cdrefs = (
            self.prefetch_zone_data_by_signature(hedges)
        )
        if not signature_map_ids:
            return self.none()

        species_filter = self.build_grouped_filter(
            signature_map_ids, observed_cdrefs
        )

        all_nearby_map_ids = set()
        for ids in signature_map_ids.values():
            all_nearby_map_ids.update(ids)
        level_label = self.build_level_subquery(list(all_nearby_map_ids))

        level_order_whens = [
            When(local_level_of_concern=value, then=Value(rank))
            for value, rank in LEVEL_OF_CONCERN_ORDER.items()
        ]

        return (
            self.filter(species_filter)
            .annotate(
                local_level_of_concern=level_label,
                observed_locally=Case(
                    When(cd_ref__in=observed_cdrefs, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                level_order=Case(
                    *level_order_whens,
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            .distinct()
            .order_by("-level_order", "common_name")
        )

    def prefetch_zone_data_by_signature(self, hedges):
        """Fetch per-signature zone data in a single DB query.

        Each zone within 400m of the hedge set is annotated with a boolean
        per signature group, indicating whether the zone is also within 400m
        of that specific group's hedges. This scopes nearby_map_ids per
        signature without adding extra DB round trips.
        """
        signature_groups = group_hedges_by_signature(hedges)
        all_hedges_geom = hedges.to_multilinestring()

        zones = Zone.objects.filter(
            geometry__dwithin=(all_hedges_geom, SPECIES_BUFFER_DISTANCE),
            map__map_type="species",
        )

        sig_annotations = {}
        sig_order = []
        for i, (sig, sig_hedges) in enumerate(signature_groups.items()):
            sig_geom = HedgeList(sig_hedges).to_multilinestring()
            annotation_name = f"near_sig_{i}"
            sig_annotations[annotation_name] = Case(
                When(
                    geometry__dwithin=(sig_geom, SPECIES_BUFFER_DISTANCE),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
            sig_order.append((annotation_name, sig))

        zones = zones.annotate(**sig_annotations)
        value_fields = ["map_id", "species_taxrefs"] + [
            name for name, _ in sig_order
        ]

        all_observed_cdrefs = set()
        signature_map_ids = {sig: set() for sig in signature_groups}

        for row in zones.values_list(*value_fields):
            map_id = row[0]
            taxrefs = row[1]
            if taxrefs:
                all_observed_cdrefs.update(taxrefs)
            for j, (_, sig) in enumerate(sig_order):
                if row[2 + j]:
                    signature_map_ids[sig].add(map_id)

        result = {
            sig: list(ids)
            for sig, ids in signature_map_ids.items()
            if ids
        }
        return result, all_observed_cdrefs

    def build_majeur_exclusion(self, observed_cdrefs):
        """Build a Q clause excluding "majeur" species not observed locally.

        "Majeur" species are only kept in the cortège when their cd_ref
        appears in the observed set. When no observations exist at all,
        every "majeur" species is excluded.
        """
        if observed_cdrefs:
            is_majeur = Q(habitats__level_of_concern="majeur")
            not_observed = ~Q(cd_ref__in=observed_cdrefs)
            return ~(is_majeur & not_observed)

        return ~Q(habitats__level_of_concern="majeur")

    def build_grouped_filter(self, signature_map_ids, observed_cdrefs):
        """Build a single Q filter from per-signature nearby map IDs.

        Each signature (hedge_type, missing_properties) has its own set of
        nearby map IDs, ensuring that a species whose habitat is only near
        hedges of type A cannot match type B's filter.
        """
        majeur_exclusion = self.build_majeur_exclusion(observed_cdrefs)

        signature_filters = [
            self.build_signature_filter(
                hedge_type, missing_props, nearby_map_ids, majeur_exclusion
            )
            for (hedge_type, missing_props), nearby_map_ids
            in signature_map_ids.items()
        ]
        return reduce(operator.or_, signature_filters)

    def build_signature_filter(
        self, hedge_type, missing_props, nearby_map_ids, majeur_exclusion
    ):
        """Build the Q filter for one (hedge_type, missing_props) signature."""
        on_nearby_map = Q(habitats__map_id__in=nearby_map_ids)
        matches_hedge_type = Q(habitats__hedge_types__contains=[hedge_type])
        signature_filter = on_nearby_map & matches_hedge_type

        if missing_props:
            requires_absent_property = Q(
                habitats__hedge_properties__overlap=list(missing_props)
            )
            signature_filter &= ~requires_absent_property

        signature_filter &= majeur_exclusion
        return signature_filter

    def build_level_subquery(self, nearby_map_ids):
        """Build a subquery to pick the highest level_of_concern per species.

        A species can appear in multiple SpeciesHabitats with different levels.
        This subquery finds the highest-ranked match and returns the label
        for display. Sorting rank is derived from the label in the outer
        query via Case/When on LEVEL_OF_CONCERN_ORDER.
        """
        best_match = (
            SpeciesHabitat.objects.filter(
                species_id=OuterRef("pk"),
                map_id__in=nearby_map_ids,
            )
            .annotate(
                level_rank=Case(
                    *LEVEL_OF_CONCERN_WHENS,
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("-level_rank")
        )
        return Subquery(best_match.values("level_of_concern")[:1])


class Species(models.Model):
    """Represent a single species."""

    # Multiple cd_nom values (unique species identifiers in the INPN TaxRef database)
    # because a single species can have been described independently by several
    # naturalists before the duplicates were recognized and merged under one cd_ref.
    cd_noms = ArrayField(
        null=True, verbose_name="CD_NOM (TaxRef)", base_field=models.IntegerField()
    )

    # Canonical TaxRef identifier — unique per species reference taxon.
    cd_ref = models.IntegerField("CD_REF TaxRef", unique=True, null=True, blank=True)

    # Some data provider (e.g Aisne) use a "group" classification that is manually
    # curated and does not match any "official" taxonomy value.
    adhoc_group = models.CharField(
        "Groupe (obsolète)",
        max_length=64,
        blank=True,
        help_text="Classification ad-hoc obsolète. Utiliser le groupe TaxRef.",
    )

    # Official group from TaxRef GROUP2_INPN field.
    group = models.CharField("Groupe", max_length=128, blank=True)

    kingdom = models.CharField("Règne", choices=KINGDOMS, max_length=32, blank=True)
    common_name = models.CharField(
        "Nom commun",
        max_length=255,
        blank=True,
        help_text="Importé depuis le référentiel TaxRef",
    )
    scientific_name = models.CharField("Nom scientifique", max_length=255, unique=True)
    level_of_concern = models.CharField(
        "Niveau d'enjeu",
        max_length=16,
        choices=LEVELS_OF_CONCERN,
        blank=True,
        help_text="Seulement pour l'Aisne. Cette valeur est désormais spécifiée dans le modèle Habitat d'espèce.",
    )
    highly_sensitive = models.BooleanField(
        "Particulièrement sensible", default=False, help_text="Seulement pour l'Aisne."
    )

    objects = models.Manager()

    # Regime unique and Droit constant use different rules to build a species list
    # We build custom manager to provide a clear api
    hru = HruSpeciesQuerySet.as_manager()
    ru = RuSpeciesQuerySet.as_manager()

    class Meta:
        verbose_name = "Espèce"
        verbose_name_plural = "Espèces"

    def __str__(self):
        if self.common_name:
            return f"{self.common_name} ({self.scientific_name})"
        return self.scientific_name


class SpeciesHabitat(models.Model):
    """Habitat requirements and conservation status of a species in a geographic area."""

    species = models.ForeignKey(
        Species,
        related_name="habitats",
        on_delete=models.CASCADE,
        verbose_name="Espèce",
    )
    map = models.ForeignKey(
        "geodata.Map",
        related_name="habitats",
        on_delete=models.CASCADE,
        verbose_name="Carte",
    )
    species_habitat_file = models.ForeignKey(
        "SpeciesHabitatFile",
        verbose_name="Importé par",
        related_name="habitats",
        null=True,
        on_delete=models.CASCADE,
    )

    hedge_types = ArrayField(
        verbose_name="Types de haies considérés",
        base_field=models.CharField(
            max_length=32,
            choices=HedgeTypeFactory.build_from_context(single_procedure=False).choices,
        ),
    )
    hedge_properties = ArrayField(
        verbose_name="Propriétés de la haie",
        help_text="Propriétés requises par l'espèce",
        base_field=models.CharField(max_length=32, choices=HEDGE_PROPERTIES),
    )
    level_of_concern = models.CharField(
        "Niveau d'enjeu local",
        max_length=16,
        choices=LEVELS_OF_CONCERN,
        null=True,
        blank=True,
        help_text="Niveau d'enjeu spécifique à cette carte/département.",
    )

    class Meta:
        verbose_name = "Habitat d'espèce"
        verbose_name_plural = "Habitats d'espèces"
        unique_together = ("species", "map")


IMPORT_STATUSES = Choices(
    ("success", "Succès"),
    ("partial_success", "Succès partiel"),
    ("failure", "Échec"),
)


class SpeciesHabitatFile(models.Model):
    """Holds a CSV file that links species and their habitat characteristics to a map."""

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
        verbose_name = "Fichier d'habitat d'espèce"
        verbose_name_plural = "Fichiers d'habitat d'espèces"

    def __str__(self):
        return self.file.name


PACAGE_RE = r"[0-9]{9}"


class Pacage(models.Model):
    """Holds data related to pacage numbers."""

    pacage_num = models.CharField(
        "Numéro de PACAGE", validators=[RegexValidator(PACAGE_RE)], primary_key=True
    )
    exploitation_density = models.DecimalField(
        "Densité de l'exploitation", max_digits=5, decimal_places=2
    )

    class Meta:
        verbose_name = "Infos Pacage"
        verbose_name_plural = "Infos Pacage"
