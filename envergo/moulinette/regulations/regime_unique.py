"""Régime unique — zone-based compensation coefficients.

Both RU evaluators call ``ensure_ru_hedge_data`` in their ``get_catalog_data``;
the first call computes the per-hedge coefficient records, the second is a no-op.
"""

from envergo.geodata.models import MAP_TYPES, Zone
from envergo.hedges.models import HedgeTypeBase, HedgeTypeFactory
from envergo.utils.fields import get_human_readable_value

# Maps (hedge_category, density_level) to the official coefficient key name.
# Numbering follows the instruction technique sent to prefects.
COEFF_KEY = {
    ("arboree", "HD"): "R3_arboree_HD",
    ("arboree", "LD"): "R4_arboree_LD",
    ("non_arboree", "HD"): "R1_non_arboree_HD",
    ("non_arboree", "LD"): "R2_non_arboree_LD",
}

# Per-hedge EP bonus added to the raw RU coefficient, keyed by (hedge_type, density).
# Only mixte/LD differs: destroying a tree-bearing hedge in a sparse landscape is
# the worst case for protected species. Kept exhaustive to mirror the instruction
# technique.
EP_RU_HEDGE_BONUS = {
    ("buissonnante", "HD"): 0.2,
    ("buissonnante", "LD"): 0.2,
    ("arbustive", "HD"): 0.2,
    ("arbustive", "LD"): 0.2,
    ("mixte", "HD"): 0.2,
    ("mixte", "LD"): 0.3,
    ("degradee", "HD"): 0.2,
    ("degradee", "LD"): 0.2,
}

# Maximum distance (metres) for nearest-zone fallback.
# This is not a business rule but a technical safeguard.
MAX_ZONE_DISTANCE_M = 50_000  # 50 km


def resolve_hedge_zones(hedges, dept_code):
    """Match each hedge to its zonage zone based on centroid containment.

    Returns ``{hedge_id: zone_attributes_dict | None}``.
    """
    if not hedges:
        return {}

    centroids = {h.id: h.geos_centroid for h in hedges}
    zones = Zone.objects.find_covering(centroids, MAP_TYPES.zonage, dept_code)

    # When a hedge doesn't fall into a zonage, we have to find the nearest zone instead.
    # Functionally, that is questionable. Zonages are administrative perimeters
    # defined by prefects, so you are either in a zonage or not.
    # But the only ways a hedge centroid might not fall into any zonage is either
    # there is a flaw in the data (e.g missing map) or the hedge topology makes
    # the centroid fall outside the department.
    # In any case we have to have a fallback.
    unmatched = {hid: centroids[hid] for hid in centroids if hid not in zones}
    if unmatched:
        nearest = Zone.objects.find_nearest_batch(
            unmatched, MAP_TYPES.zonage, dept_code, MAX_ZONE_DISTANCE_M
        )
        zones.update(nearest)

    return {
        hedge_id: zones[hedge_id].attributes if hedge_id in zones else None
        for hedge_id in centroids
    }


def zone_config_for_hedge(zone_attrs, coeff_compensation):
    """Extract (zone_id, zone_config) from zone attributes and the config dict.

    Three outcomes:

    - ``("default", config_or_none)`` when zonage is disabled (zone_attrs is
      the ``"default"`` sentinel).
    - ``(None, None)`` when no zone was matched (zone_attrs is ``None``).
    - ``(zone_id, config_or_none)`` when a zone was matched — config is
      ``None`` if ``identifiant_zone`` is missing or has no entry in
      coeff_compensation.
    """
    if zone_attrs == "default":
        return "default", coeff_compensation.get("default")

    if zone_attrs is None:
        return None, None

    zone_id = zone_attrs.get("identifiant_zone")
    zone_config = coeff_compensation.get(zone_id) if zone_id else None
    return zone_id, zone_config


def resolve_per_hedge_zone_configs(moulinette, hedges):
    """Resolve each hedge to its ``(zone_id, zone_config)`` pair.

    Performs geographic lookup (or uses the "default" sentinel when zonage
    is disabled), then maps each result through the department's
    ``coeff_compensation`` config. Returns ``{hedge_id: (zone_id, zone_config)}``.
    """
    config = moulinette.config
    coeff_compensation = config.zone_configs

    if not config.has_ru_zonage:
        matched_zones = {h.id: "default" for h in hedges}
    else:
        dept_code = moulinette.department.department
        matched_zones = resolve_hedge_zones(hedges, dept_code)

    return {
        hedge.id: zone_config_for_hedge(matched_zones[hedge.id], coeff_compensation)
        for hedge in hedges
    }


def compute_hedge_data(hedge, zone_id, zone_config, density_400):
    """Compute all coefficient data for a single hedge.

    Returns a record with zone inputs, the raw RU coefficient and the EP
    bonus. An unresolved zone (``zone_config=None``) yields a zeroed record,
    which flags the project ``non_disponible`` via ``ru_all_zones_resolved``.
    """
    if zone_config is None:
        return {
            "hedge_id": hedge.id,
            "hedge_type": hedge.hedge_type,
            "length": round(hedge.length),
            "zone_id": zone_id,
            "zone_config": None,
            "x_densite": None,
            "high_density": None,
            "raw_coefficient": 0.0,
            "ep_bonus": 0.0,
        }

    x_densite = zone_config.get("X_densite", 0.0)
    high_density = density_400 >= x_densite
    density_key = "HD" if high_density else "LD"

    # Raw RU coefficient (binary type split: mixte = arborée, rest = non arborée)
    type_key = "arboree" if hedge.hedge_type == "mixte" else "non_arboree"
    raw_coefficient = zone_config.get(COEFF_KEY[(type_key, density_key)], 0.0)

    ep_bonus = EP_RU_HEDGE_BONUS.get((hedge.hedge_type, density_key), 0.0)

    return {
        "hedge_id": hedge.id,
        "hedge_type": hedge.hedge_type,
        "length": round(hedge.length),
        "zone_id": zone_id,
        "zone_config": zone_config,
        "x_densite": x_densite,
        "high_density": high_density,
        "raw_coefficient": raw_coefficient,
        "ep_bonus": ep_bonus,
    }


def ensure_ru_hedge_data(moulinette, hedges):
    """Compute per-hedge coefficient records once, into the moulinette catalog.

    Stores ``ru_hedge_data`` ({hedge_id: record}) and ``ru_all_zones_resolved``
    (False when a hedge has no zone config → result is non_disponible).
    ``hedges`` is the evaluator's category-scoped list; both RU evaluators
    share HedgeCategory.ru, so the cached data is valid for both callers.
    """
    if "ru_hedge_data" in moulinette.catalog:
        return

    hedges = hedges.to_remove().n_alignement()
    # TODO : this density should be computed only on hedges of the evaluator category.
    haies = moulinette.catalog["haies"]
    density_400 = haies.density_around_lines.get("density_400") or 0.0

    per_hedge_zone_configs = resolve_per_hedge_zone_configs(moulinette, hedges)

    all_resolved = True
    hedge_data = {}
    for hedge in hedges:
        zone_id, zone_config = per_hedge_zone_configs[hedge.id]
        record = compute_hedge_data(hedge, zone_id, zone_config, density_400)
        if zone_config is None:
            all_resolved = False
        hedge_data[hedge.id] = record

    moulinette.catalog["ru_hedge_data"] = hedge_data
    moulinette.catalog["ru_all_zones_resolved"] = all_resolved


def collect_zone_configs(hedge_data):
    """Return a dict of distinct zone_id → zone_config from per-hedge data."""
    seen = {}
    for record in hedge_data.values():
        zone_id = record["zone_id"]
        if zone_id and zone_id not in seen and record["zone_config"] is not None:
            seen[zone_id] = record["zone_config"]
    return seen


def build_ru_hedge_detail_rows(catalog, evaluator):
    """Build per-hedge display rows from pre-computed records.

    Values are rounded for display only. ``applied_ep_bonus`` is the
    majoration actually applied (majoré − brut), not the record's potential
    ``ep_bonus``: without an effective coefficient (e.g. dispense), both EP
    columns are None and render as a dash.
    """
    hedge_data = catalog.get("ru_hedge_data", {})
    effective_coefficients = evaluator.effective_coefficients

    # RU labels (mixte → "Haie arborée") exclude degradee, which can still
    # appear in the RU category — fall back to the base enum label.
    ru_types = HedgeTypeFactory.build_from_context(single_procedure=True)

    rows = []
    for hedge_id, record in hedge_data.items():
        coeff_brut = round(record["raw_coefficient"], 2)

        if hedge_id in effective_coefficients:
            coeff_majore = round(effective_coefficients[hedge_id], 2)
            applied_ep_bonus = round(coeff_majore - coeff_brut, 2)
        else:
            coeff_majore = None
            applied_ep_bonus = None

        ru_label = get_human_readable_value(ru_types.choices, record["hedge_type"])
        base_label = get_human_readable_value(
            HedgeTypeBase.choices, record["hedge_type"]
        )

        rows.append(
            {
                "hedge_id": hedge_id,
                "hedge_type": ru_label or base_label,
                "length": record["length"],
                "zone_id": record["zone_id"],
                "x_densite": record["x_densite"],
                "high_density": record["high_density"],
                "coeff_ru_brut": coeff_brut,
                "applied_ep_bonus": applied_ep_bonus,
                "coeff_ru_majore": coeff_majore,
            }
        )
    return rows


def compute_ru_compensation_ratio(hedges, coefficients):
    """Length-weighted average of per-hedge coefficients.

    Pure function: callers pass the already-filtered hedges (to remove,
    non-alignement) and explicit coefficients.
    """
    total_length = hedges.length
    if not total_length:
        return 0.0

    compensated_length = 0.0
    for hedge in hedges:
        compensated_length += hedge.length * coefficients.get(hedge.id, 0.0)

    return round(compensated_length / total_length, 2)


def evaluator_replantation_coefficient(evaluator):
    """R for an RU evaluator: weighted average of its effective coefficients.

    Returns 0.0 outside the régime unique — the guard is defensive, since
    RU evaluators are not loaded under droit constant.
    """
    if not evaluator.moulinette.config.single_procedure:
        return 0.0
    hedges = evaluator.hedges.to_remove().n_alignement()
    return compute_ru_compensation_ratio(hedges, evaluator.effective_coefficients)
