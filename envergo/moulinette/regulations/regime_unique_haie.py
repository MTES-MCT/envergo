"""Régime unique haie — zone-based compensation coefficients.

Provides per-hedge zone resolution (mapping each hedge's centroid to a
coefficient matrix), coefficient assignment based on density and hedge type,
and a weighted-average compensation ratio used by both the régime unique
haie evaluator and the EP régime unique evaluator.
"""

from django.contrib.gis.geos import GEOSGeometry

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.utils import EPSG_LAMB93, EPSG_WGS84
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)

# Maps (hedge_category, density_level) to the official coefficient key name.
# Numbering follows the instruction technique sent to prefects.
COEFF_KEY = {
    ("arboree", "HD"): "R3_arboree_HD",
    ("arboree", "LD"): "R4_arboree_LD",
    ("non_arboree", "HD"): "R1_non_arboree_HD",
    ("non_arboree", "LD"): "R2_non_arboree_LD",
}

# Maximum distance (metres) for nearest-zone fallback.
# This is not a business rule but a technical safeguard.
MAX_ZONE_DISTANCE_M = 50_000  # 50 km


def match_point_to_zone(point, zones, zones_lamb93):
    """Return the Zone that best matches a point, or None.

    Tries containment first (GEOS ``.covers()`` on WGS84 — accurate for
    metropolitan France), then falls back to the nearest zone within 50 km
    using Lambert 93 projected distances.
    """
    for zone in zones:
        if zone.geometry.covers(point):
            return zone

    # Distance fallback — nearest zone within 50 km (Lambert 93).
    point_lamb93 = point.transform(EPSG_LAMB93, clone=True)
    best_zone = None
    min_dist = MAX_ZONE_DISTANCE_M
    for zone, zone_geom in zip(zones, zones_lamb93):
        dist = point_lamb93.distance(zone_geom)
        if dist < min_dist:
            min_dist = dist
            best_zone = zone

    return best_zone


def resolve_hedge_zones(hedges, dept_code):
    """Match each hedge to its nearest zonage Zone based on its centroid.

    Fetches all zonage zones for the department in a single DB query, then
    matches each hedge centroid in Python.

    We iterate sequentially because the number of zones per department is
    very low (a handful at best), so any clever optimization would simply
    increase complexity with few benefits.

    Returns a dict of ``hedge_id → Zone | None``.
    """
    zones = list(
        Zone.objects.filter(
            map__map_type=MAP_TYPES.zonage,
            map__departments__contains=[dept_code],
        )
    )

    if not zones:
        return {h.id: None for h in hedges}

    # Pre-compute Lambert 93 projections for the distance fallback.
    # Zone count is small, so the cost is negligible.
    zones_lamb93 = [zone.geometry.transform(EPSG_LAMB93, clone=True) for zone in zones]

    result = {}
    for hedge in hedges:
        centroid_geos = GEOSGeometry(hedge.geometry.centroid.wkt, srid=EPSG_WGS84)
        result[hedge.id] = match_point_to_zone(centroid_geos, zones, zones_lamb93)

    return result


def zone_config_for_hedge(zone, coeff_compensation):
    """Extract (zone_id, zone_config) from a matched Zone and the config dict.

    Three outcomes:

    - ``("default", config_or_none)`` when zonage is disabled (zone is the
      ``"default"`` sentinel).
    - ``(None, None)`` when no Zone was matched (zone is ``None``).
    - ``(zone_id, config_or_none)`` when a Zone was matched — config is
      ``None`` if the zone's ``identifiant_zone`` attribute is missing or
      has no entry in coeff_compensation.
    """
    if zone == "default":
        return "default", coeff_compensation.get("default")

    if zone is None:
        return None, None

    zone_id = zone.attributes.get("identifiant_zone")
    zone_config = coeff_compensation.get(zone_id) if zone_id else None
    return zone_id, zone_config


def get_ru_zone_data(moulinette):
    """Return catalog entries for per-hedge zone configs and coefficients.

    Each hedge is resolved to its own zone (based on the hedge's centroid),
    and gets its own coefficient from that zone's matrix. Because X_densite
    thresholds differ per zone, the same project-wide density_400 can classify
    as high density in one zone and low density in another.

    Returns a dict with three keys:

    - ``ru_per_hedge_coefficients``: hedge_id → coefficient (float).
    - ``ru_per_hedge_zone_info``: hedge_id → zone metadata for debug display.
    - ``ru_all_zones_resolved``: False if any hedge could not be matched to a
      zone config. Both evaluators use this to short-circuit to non_disponible.
    """
    config = moulinette.config
    settings = config.single_procedure_settings
    coeff_compensation = settings.get("coeff_compensation", {})

    haies = moulinette.catalog["haies"]
    hedges = haies.hedges_to_remove().n_alignement()

    # Resolve per-hedge zones: Zone objects when zonage is enabled,
    # the literal "default" sentinel otherwise.
    if not config.has_ru_zonage:
        matched_zones = {h.id: "default" for h in hedges}
    else:
        dept_code = moulinette.department.department
        matched_zones = resolve_hedge_zones(hedges, dept_code)

    # Assign coefficients and build per-hedge info
    density_400 = haies.density_around_lines.get("density_400") or 0.0
    coefficients = {}
    per_hedge_zone_info = {}
    all_resolved = True

    for hedge in hedges:
        zone_id, zone_config = zone_config_for_hedge(
            matched_zones[hedge.id], coeff_compensation
        )

        high_density = None
        coefficient = 0.0
        if zone_config is not None:
            x_densite = zone_config.get("X_densite", 0.0)
            high_density = density_400 >= x_densite
            density_key = "HD" if high_density else "LD"
            # "mixte" is the only RU hedge type that counts as tree-bearing
            type_key = "arboree" if hedge.hedge_type == "mixte" else "non_arboree"
            config_key = COEFF_KEY[(type_key, density_key)]
            coefficient = zone_config.get(config_key, 0.0)
        else:
            all_resolved = False

        coefficients[hedge.id] = coefficient
        per_hedge_zone_info[hedge.id] = {
            "zone_id": zone_id,
            "zone_config": zone_config,
            "high_density": high_density,
        }

    return {
        "ru_per_hedge_coefficients": coefficients,
        "ru_per_hedge_zone_info": per_hedge_zone_info,
        "ru_all_zones_resolved": all_resolved,
    }


def build_ru_debug_rows(per_hedge_zone_info, coefficients, hedges):
    """Build a list of dicts for the debug template's per-hedge zone table."""
    hedge_lengths = {h.id: h.length for h in hedges}
    rows = []
    for hedge_id, info in per_hedge_zone_info.items():
        zone_config = info["zone_config"]
        x_densite = zone_config.get("X_densite") if zone_config else None
        rows.append(
            {
                "hedge_id": hedge_id,
                "zone_id": info["zone_id"],
                "high_density": info["high_density"],
                "x_densite": x_densite,
                "length": round(hedge_lengths.get(hedge_id, 0)),
                "coefficient": coefficients.get(hedge_id, 0.0),
            }
        )
    return rows


def collect_zone_configs(per_hedge_zone_info):
    """Return a dict of distinct zone_id → zone_config from per-hedge info."""
    seen = {}
    for info in per_hedge_zone_info.values():
        zone_id = info["zone_id"]
        if zone_id and zone_id not in seen and info["zone_config"] is not None:
            seen[zone_id] = info["zone_config"]
    return seen


def get_ru_debug_context(catalog):
    """Build the RU zone debug context entries from catalog data.

    Shared by both RegimeUniqueHaie and EspecesProtegeesRegimeUnique.
    """
    per_hedge_info = catalog.get("ru_per_hedge_zone_info", {})
    coefficients = catalog.get("ru_per_hedge_coefficients", {})
    haies = catalog.get("haies")
    hedges = haies.hedges_to_remove().n_alignement() if haies else []
    return {
        "ru_hedge_rows": build_ru_debug_rows(per_hedge_info, coefficients, hedges),
        "ru_zone_configs": collect_zone_configs(per_hedge_info),
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

    # Zone data (including per-hedge coefficients) may already be in the
    # catalog if another evaluator populated it.
    if "ru_per_hedge_coefficients" not in moulinette.catalog:
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
        if self.moulinette.config.single_procedure and not self.catalog.get(
            "ru_all_zones_resolved", False
        ):
            return "non_disponible"
        return super().get_result_code(result_data)

    def get_catalog_data(self):
        """Inject density and zone-based coefficient data when in régime unique."""
        catalog = super().get_catalog_data()
        if self.moulinette.config.single_procedure:
            catalog.update(self.get_density_catalog_data())
            if "ru_per_hedge_coefficients" not in self.catalog:
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
        """Return density and per-hedge zone data for the debug template."""
        context = super().get_debug_context()
        context.update(get_ru_debug_context(self.catalog))
        return context

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        return compute_ru_compensation_ratio(self.moulinette)
