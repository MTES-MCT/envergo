"""Tests for the EspecesProtegeesRegimeUnique evaluator."""

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection
from django.test.utils import CaptureQueriesContext

from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.hedges.tests.factories import SpeciesFactory, SpeciesHabitatFactory
from envergo.moulinette.tests.factories import DCConfigHaieFactory, RUConfigHaieFactory
from envergo.moulinette.tests.utils import (
    EP_RU_DEFAULT_SETTINGS,
    make_hedge,
    make_hedge_factory,
    make_moulinette_haie_with_density,
    setup_ep_regime_unique,
    setup_regime_unique_haie,
)


@pytest.fixture
def ep_ru_criterion(france_map):
    """Create an EP regulation with a single EspecesProtegeesRegimeUnique criterion."""
    _regulation, criteria = setup_ep_regime_unique(france_map)
    return criteria


@pytest.fixture
def regime_unique_haie_criterion(france_map):
    """Create the RU haie regulation needed for replantation coefficient."""
    _regulation, criteria = setup_regime_unique_haie(france_map)
    return criteria


# ---------------------------------------------------------------------------
# Regime unique guard — step 0
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="Le critère EspecesProtegeesHorsRegimeUnique n'est pas encore spécifié"
)
def test_ep_ru_not_regime_unique_yields_non_concerne(ep_ru_criterion):
    """Department not in régime unique → non_concerne."""
    DCConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.ep.ep_regime_unique.result_code == "non_concerne"


# ---------------------------------------------------------------------------
# Cascade algorithm — project-level rules
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Le critère EspecesProtegeesL3503 n'est pas encore spécifié")
def test_ep_ru_aa_only(ep_ru_criterion):
    """All hedges are alignement → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="alignement"),
        make_hedge(hedge_id="D2", type_haie="alignement"),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    assert moulinette.ep.ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_lengths_exclude_alignements(ep_ru_criterion):
    """Lengths used in the cascade only count non-AA hedges."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="alignement"),
        make_hedge(hedge_id="D2", type_haie="buissonnante"),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    # Both hedges use the same default coordinates (~25m), so total_length
    # should reflect only the non-AA hedge, not both.
    total = moulinette.catalog["ep_ru_total_length"]
    assert total <= 30, (
        f"Expected length of a single hedge (~25m), got {total}. "
        "Alignement hedge should be excluded."
    )


def test_ep_ru_ripisylve_above_threshold(ep_ru_criterion):
    """Ripisylve length > 20m → derogation_inventaire."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="buissonnante", ripisylve=True),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    # Default hedge from COORDS_BIZOUS_INSIDE is ~25m (>20m threshold)
    assert moulinette.catalog["ep_ru_ripisylve_length"] > 20
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_short_total_dispense(ep_ru_criterion):
    """Total length <= 10m → dispense."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=8)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] <= 10
    assert moulinette.ep.ru__ep_regime_unique.result_code == "dispense"


def test_ep_ru_medium_total_moderate_density(ep_ru_criterion):
    """10m < total <= 100m and density < 80 → derogation_simplifiee."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_long_total_low_density(ep_ru_criterion):
    """Total > 100m and density < 50 → derogation_inventaire."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=40,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


# ---------------------------------------------------------------------------
# Cascade algorithm — per-hedge rules
# ---------------------------------------------------------------------------


def test_ep_ru_per_hedge_zone_sensible(ep_ru_criterion):
    """Long total + zone sensible hedge → derogation_inventaire via per-hedge."""
    RUConfigHaieFactory()
    MapFactory(
        name="Zone sensible EP",
        map_type=MAP_TYPES.zone_sensible_ep,
        zones__geometry=MultiPolygon([france_polygon]),
    )
    # density between D_BAS and D_HAUT so project-level rules don't short-circuit
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_per_hedge_short_high_density_non_mixte_dispense(ep_ru_criterion):
    """Short total + high density + non-mixte + no zone → dispense via per-hedge.

    Reaches step 6 with total ∈ (L_BAS, L_HAUT] and density > D_HAUT, where
    the per-hedge dispense branch is exercised.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=50, type_haie="buissonnante")],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "dispense"


def test_ep_ru_per_hedge_short_high_density_mixte_no_dispense(ep_ru_criterion):
    """Short total + high density + mixte + no zone → derogation_simplifiee.

    Mixte hedges are excluded from the per-hedge dispense branch even when
    every other condition is met.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=50, type_haie="mixte")],
        reimplantation="replantation",
    )
    total = moulinette.catalog["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_long_high_density_no_dispense(ep_ru_criterion):
    """Long total + high density + no zone → derogation_simplifiee.

    Regression: long-total projects must NOT fall into the dispense branch,
    even with high density and no sensitive zone. The L_HAUT cap on the
    dispense path was missing in an earlier version of the spec.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=90,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_fallback_derogation_simplifiee(ep_ru_criterion):
    """Medium density, long total, no zone sensible → derogation_simplifiee."""
    RUConfigHaieFactory()
    # density between D_BAS and D_HAUT, no zone sensible → fallback
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


# ---------------------------------------------------------------------------
# Replantation coefficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length, density, expected_code, expected_coeff",
    [
        (8, 60, "dispense", 0.0),  # dispense → no compensation
        (
            50,
            60,
            "derogation_simplifiee",
            1.7,
        ),  # R_ru=1.5 + bonus=0.2 (buissonnante HD)
        (
            120,
            40,
            "derogation_inventaire",
            1.7,
        ),  # R_ru=1.5 + bonus=0.2 (buissonnante LD)
    ],
)
def test_ep_ru_replantation_coefficient(
    ep_ru_criterion,
    regime_unique_haie_criterion,
    length,
    density,
    expected_code,
    expected_coeff,
):
    """Replantation coefficient = R_ru + per-hedge type/density bonus."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=density,
        hedges=[make_hedge_factory(length=length)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    assert criterion.result_code == expected_code
    assert criterion.get_evaluator().get_replantation_coefficient() == expected_coeff


# ---------------------------------------------------------------------------
# Sensitive species — no longer affect coefficients
# ---------------------------------------------------------------------------


def test_ep_ru_sensitive_species_do_not_affect_coefficient(
    ep_ru_criterion,
    regime_unique_haie_criterion,
):
    """Sensitive species presence does not change the replantation coefficient."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    assert criterion.result_code == "derogation_simplifiee"

    evaluator = criterion.get_evaluator()
    coeff_before = evaluator.get_replantation_coefficient()

    evaluator.catalog["has_sensitive_species"] = True
    evaluator.evaluate()
    assert evaluator.get_replantation_coefficient() == coeff_before


# ---------------------------------------------------------------------------
# Settings form (admin-configurable thresholds)
# ---------------------------------------------------------------------------


def test_ep_ru_missing_settings_yields_non_disponible(france_map):
    """Empty evaluator_settings → criterion result is non_disponible."""
    setup_ep_regime_unique(france_map, evaluator_settings={})
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.ep.ru__ep_regime_unique.result_code == "non_disponible"


def test_ep_ru_settings_override_thresholds(france_map):
    """Overriding l_haut shifts a project from step 4 into step 6 territory.

    With the default l_haut=100, a 50 m project hits step 4
    (derogation_simplifiee). Lowering l_haut to 30 makes the same project
    "long", and combined with high density it falls into step 5
    (derogation_inventaire).
    """
    custom = dict(EP_RU_DEFAULT_SETTINGS, l_haut=30, d_bas=80)
    setup_ep_regime_unique(france_map, evaluator_settings=custom)
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    assert moulinette.catalog["ep_ru_total_length"] > 30
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


# ---------------------------------------------------------------------------
# Species cortege — public vs. sensitive split
# ---------------------------------------------------------------------------

# Default HedgeFactory places hedges near (lng=3.584, lat=43.687).
# This polygon covers that area so RU zone queries find it within 400m.
HEDGE_AREA_POLYGON = Polygon(
    [
        (3.580, 43.685),
        (3.590, 43.685),
        (3.590, 43.690),
        (3.580, 43.690),
        (3.580, 43.685),
    ]
)


def setup_species_near_hedges(levels):
    """Create species with SpeciesHabitats on a map whose zone overlaps the default hedge area.

    `levels` is a list of (cd_ref, level_of_concern) tuples. Returns the
    created species list.
    """
    map_obj = MapFactory(map_type="species", zones=None)
    cd_refs = [cd_ref for cd_ref, _ in levels]
    ZoneFactory(
        map=map_obj,
        geometry=MultiPolygon([HEDGE_AREA_POLYGON]),
        species_taxrefs=cd_refs,
    )
    species_list = []
    for cd_ref, level in levels:
        sp = SpeciesFactory(cd_ref=cd_ref)
        SpeciesHabitatFactory(
            species=sp,
            map=map_obj,
            hedge_types=["degradee", "buissonnante", "arbustive", "mixte"],
            level_of_concern=level,
        )
        species_list.append(sp)
    return species_list


def test_ep_ru_catalog_no_sensitive_species(ep_ru_criterion):
    """When no species have level 'majeur', has_sensitive_species is False
    and the public list equals the full list."""
    RUConfigHaieFactory()
    setup_species_near_hedges(
        [
            (9001, "fort"),
            (9002, "moyen"),
        ]
    )

    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    catalog = moulinette.catalog

    assert catalog["has_sensitive_species"] is False
    full = catalog["protected_species"]
    public = catalog["protected_species_public"]
    assert len(full) == len(public)
    assert {s.cd_ref for s in full} == {s.cd_ref for s in public}


def test_ep_ru_catalog_with_sensitive_species(ep_ru_criterion):
    """When some species have level 'majeur', they are excluded from the public list."""
    RUConfigHaieFactory()
    setup_species_near_hedges(
        [
            (9003, "fort"),
            (9004, "majeur"),
        ]
    )

    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    catalog = moulinette.catalog

    assert catalog["has_sensitive_species"] is True

    full_refs = {s.cd_ref for s in catalog["protected_species"]}
    public_refs = {s.cd_ref for s in catalog["protected_species_public"]}
    assert 9003 in full_refs
    assert 9004 in full_refs
    assert 9003 in public_refs
    assert 9004 not in public_refs


# Effective coefficients (post-evaluate hook)
# ---------------------------------------------------------------------------


def test_ep_ru_effective_coefficients_include_bonus(
    ep_ru_criterion,
    regime_unique_haie_criterion,
):
    """The effective_coefficients property returns raw + per-hedge type/density bonus."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    evaluator = criterion.get_evaluator()
    assert criterion.result_code == "derogation_simplifiee"

    effective = evaluator.effective_coefficients
    hedge_data = moulinette.catalog["ru_hedge_data"]

    # Default hedge is buissonnante, density=60 >= X_densite=60 → HD → bonus=0.2
    for hedge_id, record in hedge_data.items():
        assert effective[hedge_id] == record["raw_coefficient"] + 0.2


@pytest.mark.parametrize(
    "type_haie, density, expected_bonus",
    [
        ("mixte", 40, 0.3),  # arborée + LD: the only entry that differs
        ("mixte", 60, 0.2),  # arborée + HD (60 >= X_densite=60)
        ("arbustive", 40, 0.2),
        ("arbustive", 60, 0.2),
    ],
)
def test_ep_ru_bonus_depends_on_type_and_density(
    ep_ru_criterion,
    regime_unique_haie_criterion,
    type_haie,
    density,
    expected_bonus,
):
    """The EP bonus varies with hedge type and HD/LD classification."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=density,
        hedges=[make_hedge_factory(length=50, type_haie=type_haie)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    assert criterion.result_code == "derogation_simplifiee"

    effective = criterion.get_evaluator().effective_coefficients
    hedge_data = moulinette.catalog["ru_hedge_data"]

    for hedge_id, record in hedge_data.items():
        assert effective[hedge_id] == record["raw_coefficient"] + expected_bonus


def test_ep_ru_effective_coefficients_diverge_from_ru(
    ep_ru_criterion,
    regime_unique_haie_criterion,
):
    """EPRU effective coefficients include the EP bonus; RU's do not.

    Both evaluators share the same ru_hedge_data. After evaluate(),
    EPRU's effective_coefficients adds the bonus while RU's returns
    the raw values unchanged.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    hedge_data = moulinette.catalog["ru_hedge_data"]

    ep_evaluator = moulinette.ep.ru__ep_regime_unique.get_evaluator()
    ep_effective = ep_evaluator.effective_coefficients

    ru_evaluator = moulinette.regime_unique_haie.ru__regime_unique_haie.get_evaluator()
    ru_effective = ru_evaluator.effective_coefficients

    for hedge_id, record in hedge_data.items():
        raw = record["raw_coefficient"]
        assert ep_effective[hedge_id] > raw
        assert ru_effective[hedge_id] == raw


def test_ep_ru_dispense_effective_empty(
    ep_ru_criterion,
    regime_unique_haie_criterion,
):
    """Dispense result → effective coefficients are empty and R is 0."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=8)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    assert criterion.result_code == "dispense"

    evaluator = criterion.get_evaluator()
    assert evaluator.effective_coefficients == {}
    assert evaluator.get_replantation_coefficient() == 0.0


def test_ru_zone_query_runs_once(
    france_map,
    ep_ru_criterion,
    regime_unique_haie_criterion,
):
    """Both evaluators share ru_hedge_data — the zone query runs only once."""
    zonage_map = MapFactory(map_type=MAP_TYPES.zonage, departments=["44"], zones=[])
    ZoneFactory(
        map=zonage_map,
        geometry=MultiPolygon([france_polygon]),
        attributes={"identifiant_zone": "zone_A"},
    )
    single_procedure_settings = {
        "coeff_compensation": {
            "zone_A": {
                "X_densite": 60,
                "R1_buissonnante_HD": 1.5,
                "R2_buissonnante_LD": 1.5,
                "R3_arbustive_HD": 1.5,
                "R4_arbustive_LD": 1.5,
                "R5_arboree_HD": 1.5,
                "R6_arboree_LD": 1.5,
            }
        }
    }
    RUConfigHaieFactory(
        single_procedure_settings=single_procedure_settings, has_ru_zonage=True
    )

    with CaptureQueriesContext(connection) as ctx:
        moulinette = make_moulinette_haie_with_density(
            density=60,
            hedges=[make_hedge_factory(length=50)],
            reimplantation="replantation",
        )

    assert "ru_hedge_data" in moulinette.catalog

    zone_queries = [q for q in ctx.captured_queries if "ST_Covers" in q["sql"]]
    assert len(zone_queries) == 1
