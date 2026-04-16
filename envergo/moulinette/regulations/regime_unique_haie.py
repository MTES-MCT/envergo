"""Régime unique haie — zone-based compensation coefficients.

Provides zone resolution (mapping a project's location to a coefficient
matrix), per-hedge coefficient assignment based on density and hedge type,
and a weighted-average compensation ratio used by both the régime unique
haie evaluator and the EP régime unique evaluator.
"""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import GEOSGeometry

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)

# Maps (hedge_category, density_level) to the official coefficient key name.
# Numbering follows the instruction technique sent to prefects.
_COEFF_KEY = {
    ("arboree", "HD"): "R3_arboree_HD",
    ("arboree", "LD"): "R4_arboree_LD",
    ("non_arboree", "HD"): "R1_non_arboree_HD",
    ("non_arboree", "LD"): "R2_non_arboree_LD",
}


def resolve_zone_config(moulinette):
    """Return the ``(zone_id, zone_config)`` pair for the project's location.

    Three possible outcomes:
    - ``("default", {...})``: zonage disabled — uses the default matrix.
    - ``(zone_id, {...})``: zonage enabled, matching zone found.
    - ``(zone_id_or_none, None)``: zonage enabled but no matching zone
      or no config entry for the found zone.
    """
    config = moulinette.config
    settings = config.single_procedure_settings
    coeff_compensation = settings.get("coeff_compensation", {})

    if not config.has_ru_zonage:
        return "default", coeff_compensation.get("default", {})

    haies = moulinette.catalog["haies"]
    centroid_shapely = haies.get_centroid_to_remove()
    centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)

    dept_code = moulinette.department.department

    # Single distance query: containing zones have distance=0.
    # This bypasses the GiST index (no geometry__covers filter), but the number of
    # zonage rows per department is small enough that a sequential distance scan
    # is negligible.
    zonage = (
        Zone.objects.filter(
            map__map_type=MAP_TYPES.zonage,
            map__departments__contains=[dept_code],
        )
        .annotate(distance=Distance("geometry", centroid_geos))
        .order_by("distance")
        .defer("geometry")
        .first()
    )

    zone_id = None
    zone_config = None
    if zonage is not None:
        zone_id = zonage.attributes.get("identifiant_zone")
        if zone_id and zone_id in coeff_compensation:
            zone_config = coeff_compensation[zone_id]

    return zone_id, zone_config


def get_ru_zone_data(moulinette):
    """Return catalog entries for the RU zone config and per-hedge coefficients."""
    zone_id, zone_config = resolve_zone_config(moulinette)

    high_density = None
    coefficients = {}
    if zone_config is not None:
        haies = moulinette.catalog["haies"]
        density_400 = haies.density_around_lines.get("density_400") or 0.0
        x_densite = zone_config.get("X_densite", 0.0)
        high_density = density_400 >= x_densite

        density_key = "HD" if high_density else "LD"
        for hedge in haies.hedges_to_remove().n_alignement():
            # "mixte" is the only RU hedge type that counts as tree-bearing ("arborée")
            type_key = "arboree" if hedge.hedge_type == "mixte" else "non_arboree"
            config_key = _COEFF_KEY[(type_key, density_key)]
            coefficients[hedge.id] = zone_config.get(config_key, 0.0)

    return {
        "ru_zone_id": zone_id,
        "ru_zone_config": zone_config,
        "ru_high_density": high_density,
        "ru_per_hedge_coefficients": coefficients,
    }


def compute_ru_compensation_ratio(moulinette):
    """Compute the régime unique compensation ratio.

    Returns the weighted average of per-hedge compensation coefficients
    (zone-aware, density-sensitive), weighted by hedge length. Alignements
    are excluded. Returns 0.0 when the department is not in régime unique.
    """
    if not moulinette.config.single_procedure:
        return 0.0

    haies = moulinette.catalog["haies"]
    hedges = haies.hedges_to_remove().n_alignement()
    total_length = hedges.length
    if not total_length:
        return 0.0

    # The method could be called by several evaluators so the zonage config
    # might already be in the catalog
    if "ru_zone_config" not in moulinette.catalog:
        moulinette.catalog.update(get_ru_zone_data(moulinette))
    coefficients = moulinette.catalog["ru_per_hedge_coefficients"]

    compensated_length = 0.0
    for hedge in hedges:
        compensated_length += hedge.length * coefficients.get(hedge.id, 0.0)

    return round(compensated_length / total_length, 2)


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    """Regulation-level evaluator for the régime unique haie procedure."""

    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaie(PlantationConditionMixin, HedgeDensityMixin, CriterionEvaluator):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    plantation_conditions = []

    RESULT_MATRIX = {
        "non_disponible": RESULTS.non_disponible,
        "non_concerne": RESULTS.non_concerne,
        "non_concerne_aa": RESULTS.non_concerne,
        "soumis": RESULTS.soumis,
    }

    CODE_MATRIX = {
        ("regime_unique", "aa_only"): "non_concerne_aa",
        ("regime_unique", "has_hedges"): "soumis",
        ("droit_constant", "aa_only"): "non_concerne",
        ("droit_constant", "has_hedges"): "non_concerne",
    }

    def get_result_code(self, result_data):
        """Override to detect missing zone config before the CODE_MATRIX lookup."""
        if (
            self.moulinette.config.single_procedure
            and self.catalog.get("ru_zone_config") is None
        ):
            return "non_disponible"
        return super().get_result_code(result_data)

    def get_catalog_data(self):
        """Inject density and zone-based coefficient data when in régime unique."""
        catalog = super().get_catalog_data()
        if self.moulinette.config.single_procedure:
            catalog.update(self.get_density_catalog_data())
            if "ru_zone_config" not in self.catalog:
                catalog.update(get_ru_zone_data(self.moulinette))
        return catalog

    def get_result_data(self):
        """Return a (procedure_mode, hedge_presence) tuple for CODE_MATRIX lookup."""
        hedges = self.catalog["haies"].hedges_to_remove()
        has_hedges = any(h for h in hedges if h.hedge_type != "alignement")
        regime_unique = self.moulinette.config.single_procedure

        procedure_mode = "regime_unique" if regime_unique else "droit_constant"
        hedge_presence = "has_hedges" if has_hedges else "aa_only"
        return procedure_mode, hedge_presence

    def get_debug_context(self):
        """Return density and RU zone data for the debug template."""
        context = super().get_debug_context()
        context["ru_zone_id"] = self.catalog.get("ru_zone_id")
        context["ru_zone_config"] = self.catalog.get("ru_zone_config")
        context["ru_high_density"] = self.catalog.get("ru_high_density")
        context["ru_per_hedge_coefficients"] = self.catalog.get(
            "ru_per_hedge_coefficients"
        )
        return context

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        return compute_ru_compensation_ratio(self.moulinette)
