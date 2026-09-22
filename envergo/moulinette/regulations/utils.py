"""Per-hedge compensation coefficients for the régime unique."""

import logging

from envergo.geodata.models import MAP_TYPES, Zone
from envergo.hedges.models import HedgeTypeBase, HedgeTypeFactory
from envergo.utils.fields import get_human_readable_value

logger = logging.getLogger(__name__)

# Maps (hedge_category, density_level) to the official coefficient key name.
# Coefficient key names follow the numbering of the instruction technique sent to prefects.
COEFF_KEY = {
    ("buissonnante", "HD"): "R1_buissonnante_HD",
    ("buissonnante", "LD"): "R2_buissonnante_LD",
    ("arbustive", "HD"): "R3_arbustive_HD",
    ("arbustive", "LD"): "R4_arbustive_LD",
    ("arboree", "HD"): "R5_arboree_HD",
    ("arboree", "LD"): "R6_arboree_LD",
}

# Missing types (degradee, alignement) have no RU coefficient.
HEDGE_TYPE_TO_COEFF_CATEGORY = {
    "buissonnante": "buissonnante",
    "arbustive": "arbustive",
    "mixte": "arboree",
}


def resolve_coeff_category(hedge_type):
    """Return the RU coefficient category of a hedge type.

    Raises ValueError when the type has none.
    """
    try:
        return HEDGE_TYPE_TO_COEFF_CATEGORY[hedge_type]
    except KeyError:
        raise ValueError(
            f"Type de haie « {hedge_type} » invalide pour le régime unique : "
            "le calcul du coefficient de compensation n'est défini que pour "
            "les haies buissonnantes, arbustives et mixtes."
        )


# Per hedge EP bonus added to the raw RU coefficient.
# Destroying mixte hedges in low-density zones have a higher impact
# for protected species, hence the bigger bonus.
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
    """Match each hedge centroid to a zone. Return ``{hedge_id: zone attributes | None}``."""
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
    """Return ``(zone_id, zone_config)`` for matched zone attributes.

    ``zone_attrs`` is ``"default"`` when the department has no zonage.
    A ``None`` zone_id means no zone matched.
    A ``None`` config means the zone has no coefficient entry.
    """
    if zone_attrs == "default":
        return "default", coeff_compensation.get("default")

    if zone_attrs is None:
        return None, None

    zone_id = zone_attrs.get("identifiant_zone")
    zone_config = coeff_compensation.get(zone_id) if zone_id else None
    return zone_id, zone_config


def resolve_per_hedge_zone_configs(moulinette, hedges):
    """Return ``{hedge_id: (zone_id, zone_config)}``. See ``zone_config_for_hedge``."""
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


def _unresolved_hedge_record(hedge, zone_id):
    """Zeroed record for a hedge that cannot be scored."""
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


def compute_hedge_data(hedge, zone_id, zone_config, density_400):
    """Return the coefficient record of one hedge to remove.

    Some hedges cannot be scored: no zone config, or a type without RU coefficient.
    They get a zeroed record with ``zone_config=None``.
    """
    if zone_config is None:
        return _unresolved_hedge_record(hedge, zone_id)

    try:
        type_key = resolve_coeff_category(hedge.hedge_type)
    except ValueError:
        # This should never happen in an RU department. Log it so Sentry sees it.
        logger.exception(
            "Haie %s de type « %s » classée en régime unique sans coefficient "
            "RU défini : résultat non disponible.",
            hedge.id,
            hedge.hedge_type,
        )
        return _unresolved_hedge_record(hedge, zone_id)

    x_densite = zone_config.get("X_densite", 0.0)
    high_density = density_400 >= x_densite
    density_key = "HD" if high_density else "LD"

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
    """Store ``ru_hedge_data`` and ``ru_all_zones_resolved`` in the catalog.

    Runs once. Every caller passes the same ``HedgeCategory.ru`` hedges, so the
    first result is valid for all of them.
    """
    if "ru_hedge_data" in moulinette.catalog:
        return

    hedges = hedges.to_remove().n_alignement()
    haies = moulinette.catalog["haies"]
    density_400 = (
        haies.density_around_lines(hedges.to_remove()).get("density_400") or 0.0
    )

    per_hedge_zone_configs = resolve_per_hedge_zone_configs(moulinette, hedges)

    all_resolved = True
    hedge_data = {}
    for hedge in hedges:
        zone_id, zone_config = per_hedge_zone_configs[hedge.id]
        record = compute_hedge_data(hedge, zone_id, zone_config, density_400)
        if record["zone_config"] is None:
            all_resolved = False
        hedge_data[hedge.id] = record

    moulinette.catalog["ru_hedge_data"] = hedge_data
    moulinette.catalog["ru_all_zones_resolved"] = all_resolved


def collect_zone_configs(hedge_data):
    """Return a dict of distinct zone_id -> zone_config from per-hedge data."""
    seen = {}
    for record in hedge_data.values():
        zone_id = record["zone_id"]
        if zone_id and zone_id not in seen and record["zone_config"] is not None:
            seen[zone_id] = record["zone_config"]
    return seen


def build_ru_hedge_detail_rows(catalog, evaluator):
    """Build per-hedge display rows from the catalog records.

    ``applied_ep_bonus`` is the bonus the evaluator really applied.
    It differs from the record's ``ep_bonus``, which is only potential.
    It is ``None`` when no coefficient is due.
    """
    hedge_data = catalog.get("ru_hedge_data", {})
    effective_coefficients = evaluator.effective_coefficients

    # RU labels have no degradee entry. That type can still appear in the RU category.
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

    ``hedges`` must contain only hedges to remove, without alignements.
    """
    total_length = hedges.length
    if not total_length:
        return 0.0

    compensated_length = 0.0
    for hedge in hedges:
        compensated_length += hedge.length * coefficients.get(hedge.id, 0.0)

    return round(compensated_length / total_length, 2)


def evaluator_replantation_coefficient(evaluator):
    """Return the evaluator's R.

    R is the length-weighted average of its effective coefficients.
    It is 0.0 outside the régime unique.
    """
    if not evaluator.moulinette.config.single_procedure:
        return 0.0
    hedges = evaluator.hedges.to_remove().n_alignement()
    return compute_ru_compensation_ratio(hedges, evaluator.effective_coefficients)
