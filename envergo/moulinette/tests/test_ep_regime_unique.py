"""Tests for the EspecesProtegeesRu evaluator."""

from math import ceil

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection
from django.template import Context, Template
from django.test.utils import CaptureQueriesContext

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.hedges.models import HedgeCategory, Species
from envergo.hedges.regulations import RUMinLengthCondition, SafetyCondition
from envergo.hedges.services import PlantationEvaluator
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
from envergo.petitions.regulations.ep import ep_regulation_get_instructor_view_context


@pytest.fixture
def ep_ru_criteria(france_map):
    """Create an EP regulation with the three criteria (RU, HRU, L350-3)."""
    _regulation, criteria = setup_ep_regime_unique(france_map)
    return criteria


@pytest.fixture
def regime_unique_haie_criterion(france_map):
    """Create the RU haie regulation needed for replantation coefficient."""
    _regulation, criteria = setup_regime_unique_haie(france_map)
    return criteria


def ep_ru_catalog(moulinette):
    """The data computed by the EP régime unique evaluator."""
    return moulinette.ep.ru__ep_regime_unique.catalog


# ---------------------------------------------------------------------------
# Regime unique guard — step 0
# ---------------------------------------------------------------------------


def test_ep_ru_not_activated_outside_regime_unique(ep_ru_criteria):
    """Outside the régime unique, no hedge lands in the RU category.

    The criterion is therefore never activated, and the EP regulation has no
    result for that category.
    """
    DCConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    slugs = [criterion.slug for criterion in moulinette.ep.criteria.all()]
    assert "ru__ep_regime_unique" not in slugs
    assert HedgeCategory.ru not in moulinette.results_by_category


# ---------------------------------------------------------------------------
# Cascade algorithm — project-level rules
# ---------------------------------------------------------------------------


def test_ep_ru_aa_only(ep_ru_criteria):
    """All hedges are roadside alignements → only the L350-3 criterion applies."""
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
    assert moulinette.ep.l350_3__ep_regime_unique.result_code == "a_verifier"
    # No RU hedge at all: the category is dropped from the displayed results.
    assert HedgeCategory.ru not in moulinette.results_by_category


def test_ep_ru_lengths_exclude_alignements(ep_ru_criteria):
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
    total = ep_ru_catalog(moulinette)["ep_ru_total_length"]
    assert total <= 30, (
        f"Expected length of a single hedge (~25m), got {total}. "
        "Alignement hedge should be excluded."
    )


def test_ep_ru_ripisylve_above_threshold(ep_ru_criteria):
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
    assert ep_ru_catalog(moulinette)["ep_ru_ripisylve_length"] > 20
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_short_total_dispense(ep_ru_criteria):
    """Total length <= 10m → dispense."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=8)],
        reimplantation="replantation",
    )
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] <= 10
    assert moulinette.ep.ru__ep_regime_unique.result_code == "dispense"


def test_ep_ru_medium_total_moderate_density(ep_ru_criteria):
    """10m < total <= 100m and density < 80 → derogation_simplifiee."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=[make_hedge_factory(length=50)],
        reimplantation="replantation",
    )
    total = ep_ru_catalog(moulinette)["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_long_total_low_density(ep_ru_criteria):
    """Total > 100m and density < 50 → derogation_inventaire."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=40,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


# ---------------------------------------------------------------------------
# Cascade algorithm — per-hedge rules
# ---------------------------------------------------------------------------


def test_ep_ru_per_hedge_zone_sensible(ep_ru_criteria):
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
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_inventaire"


def test_ep_ru_per_hedge_short_high_density_non_mixte_dispense(ep_ru_criteria):
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
    total = ep_ru_catalog(moulinette)["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "dispense"


def test_ep_ru_per_hedge_short_high_density_mixte_no_dispense(ep_ru_criteria):
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
    total = ep_ru_catalog(moulinette)["ep_ru_total_length"]
    assert 10 < total <= 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_long_high_density_no_dispense(ep_ru_criteria):
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
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] > 100
    assert moulinette.ep.ru__ep_regime_unique.result_code == "derogation_simplifiee"


def test_ep_ru_per_hedge_fallback_derogation_simplifiee(ep_ru_criteria):
    """Medium density, long total, no zone sensible → derogation_simplifiee."""
    RUConfigHaieFactory()
    # density between D_BAS and D_HAUT, no zone sensible → fallback
    moulinette = make_moulinette_haie_with_density(
        density=65,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] > 100
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
    ep_ru_criteria,
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
    ep_ru_criteria,
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
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] > 30
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


DEFAULT_HABITAT_HEDGE_TYPES = ["degradee", "buissonnante", "arbustive", "mixte"]


def setup_species_near_hedges(levels, hedge_types=None):
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
            hedge_types=hedge_types or DEFAULT_HABITAT_HEDGE_TYPES,
            level_of_concern=level,
        )
        species_list.append(sp)
    return species_list


def test_ep_ru_catalog_no_sensitive_species(ep_ru_criteria):
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
    catalog = ep_ru_catalog(moulinette)

    assert catalog["has_sensitive_species"] is False
    full = catalog["protected_species"]
    public = catalog["protected_species_public"]
    assert len(full) == len(public)
    assert {s.cd_ref for s in full} == {s.cd_ref for s in public}


def test_ep_ru_catalog_with_sensitive_species(ep_ru_criteria):
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
    catalog = ep_ru_catalog(moulinette)

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
    ep_ru_criteria,
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
    ep_ru_criteria,
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
    ep_ru_criteria,
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
    ep_ru_criteria,
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
    ep_ru_criteria,
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


# ---------------------------------------------------------------------------
# Multi-category projects — hedge scoping
# ---------------------------------------------------------------------------


def make_multi_category_hedges():
    """One hedge to remove per category, plus one hedge to plant per category."""
    return [
        make_hedge(hedge_id="D1", type_haie="buissonnante"),
        make_hedge(hedge_id="D2", type_haie="alignement", bord_voie=True),
        make_hedge(hedge_id="D3", type_haie="alignement", bord_voie=False),
        make_hedge(hedge_id="P1", hedge_type="TO_PLANT", type_haie="buissonnante"),
        make_hedge(
            hedge_id="P2", hedge_type="TO_PLANT", type_haie="alignement", bord_voie=True
        ),
        make_hedge(
            hedge_id="P3",
            hedge_type="TO_PLANT",
            type_haie="alignement",
            bord_voie=False,
        ),
    ]


def test_ep_ru_only_evaluates_ru_hedges(ep_ru_criteria):
    """The RU criterion sees RU hedges only, both to remove and to plant."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=make_multi_category_hedges(),
        reimplantation="replantation",
    )
    evaluator = moulinette.ep.ru__ep_regime_unique.get_evaluator()

    assert {h.id for h in evaluator.hedges.to_remove()} == {"D1"}
    assert {h.id for h in evaluator.hedges.to_plant()} == {"P1"}


def test_ep_ru_lengths_only_count_ru_hedges(ep_ru_criteria):
    """Cascade lengths ignore the hedges of the other two categories."""
    RUConfigHaieFactory()
    hedge_data = [
        make_hedge(hedge_id="D1", type_haie="buissonnante"),
        make_hedge(hedge_id="D2", type_haie="alignement", bord_voie=True),
        make_hedge(hedge_id="D3", type_haie="alignement", bord_voie=False),
    ]
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=hedge_data,
        reimplantation="replantation",
    )
    ru_length = moulinette.catalog["haies"].hedges().ru().to_remove().length
    assert ep_ru_catalog(moulinette)["ep_ru_total_length"] == ceil(ru_length)


# ---------------------------------------------------------------------------
# HRU and L350-3 criteria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["hru__ep_regime_unique", "l350_3__ep_regime_unique"])
def test_ep_non_ru_categories_are_always_a_verifier(ep_ru_criteria, slug):
    """Neither length nor hedge type changes the result: always "à vérifier"."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=make_multi_category_hedges(),
        reimplantation="replantation",
    )
    criterion = getattr(moulinette.ep, slug)
    assert criterion.result_code == "a_verifier"
    assert criterion.result == RESULTS.a_verifier


@pytest.mark.parametrize(
    "slug, expected_r, has_min_length_condition",
    [("hru__ep_regime_unique", 1.0, True), ("l350_3__ep_regime_unique", 0.0, False)],
)
def test_ep_non_ru_categories_have_min_length_and_safety_conditions(
    ep_ru_criteria, slug, expected_r, has_min_length_condition
):
    """The minimum length uses the category's own R, with the safety check and no
    hedge type requirement."""
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=make_multi_category_hedges(),
        reimplantation="replantation",
    )
    evaluator = getattr(moulinette.ep, slug).get_evaluator()

    assert SafetyCondition in evaluator.plantation_conditions
    if has_min_length_condition:
        assert RUMinLengthCondition in evaluator.plantation_conditions
    assert evaluator.get_replantation_coefficient() == expected_r

    conditions = evaluator.plantation_evaluate(expected_r)
    if has_min_length_condition:
        assert [type(c) for c in conditions] == [RUMinLengthCondition, SafetyCondition]
    else:
        assert [type(c) for c in conditions] == [SafetyCondition]


def setup_per_category_species():
    """One species only found in RU hedges, one only found in tree alignments."""
    setup_species_near_hedges([(9201, "fort")], hedge_types=["buissonnante"])
    setup_species_near_hedges([(9202, "majeur")], hedge_types=["alignement"])


def make_ru_and_l350_3_hedges():
    return [
        make_hedge_factory(length=50, type_haie="buissonnante"),
        make_hedge_factory(
            length=50, type_haie="alignement", additionalData__bord_voie=True
        ),
    ]


def test_ep_non_ru_categories_compute_their_own_cortege(ep_ru_criteria):
    """Each criterion catalog holds the species of its own hedges only."""
    RUConfigHaieFactory()
    setup_per_category_species()

    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=make_ru_and_l350_3_hedges(),
        reimplantation="replantation",
    )

    ru = moulinette.ep.ru__ep_regime_unique.catalog
    assert {s.cd_ref for s in ru["protected_species"]} == {9201}
    assert {s.cd_ref for s in ru["protected_species_public"]} == {9201}
    assert ru["has_sensitive_species"] is False

    l350_3 = moulinette.ep.l350_3__ep_regime_unique.catalog
    assert {s.cd_ref for s in l350_3["protected_species"]} == {9202}
    # "majeur" species stay out of the list shown to the petitioner
    assert l350_3["protected_species_public"] == []
    assert l350_3["has_sensitive_species"] is True


def test_ep_instructor_species_cover_the_whole_project(ep_ru_criteria):
    """The instruction page lists the species of every EP criterion.

    Criteria contexts are merged in order, so the project-wide list is built by
    the regulation-level context getter, which is applied last.
    """
    RUConfigHaieFactory()
    setup_per_category_species()

    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=make_ru_and_l350_3_hedges(),
        reimplantation="replantation",
    )

    context = ep_regulation_get_instructor_view_context(
        moulinette.ep.get_evaluator(), None, moulinette
    )
    assert {s.cd_ref for s in context["protected_species"]} == {9201, 9202}
    assert context["has_sensitive_species"] is True


# ---------------------------------------------------------------------------
# Safety condition across categories
# ---------------------------------------------------------------------------


def make_hedges_with_plantation(unsafe_l350_3):
    """An RU and an L350-3 hedge to remove, with one hedge to plant each."""
    return [
        make_hedge(hedge_id="D1", type_haie="mixte"),
        make_hedge(hedge_id="D2", type_haie="alignement", bord_voie=True),
        make_hedge(
            hedge_id="P1",
            hedge_type="TO_PLANT",
            type_haie="buissonnante",
            sous_ligne_electrique=False,
        ),
        make_hedge(
            hedge_id="P2",
            hedge_type="TO_PLANT",
            type_haie="alignement",
            bord_voie=True,
            sous_ligne_electrique=unsafe_l350_3,
        ),
    ]


@pytest.mark.parametrize("unsafe_l350_3, expected", [(False, True), (True, False)])
def test_safety_condition_covers_every_category(
    ep_ru_criteria, unsafe_l350_3, expected
):
    """A failing safety check in one category is not hidden by a passing one.

    Each EP criterion only sees the hedges of its own category, so the
    deduplicated condition must be the failing one whenever any category fails.
    """
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedge_data=make_hedges_with_plantation(unsafe_l350_3),
        reimplantation="replantation",
    )
    evaluation = PlantationEvaluator(moulinette, moulinette.catalog["haies"])

    safety_conditions = [
        c for c in evaluation.conditions if isinstance(c, SafetyCondition)
    ]
    assert len(safety_conditions) == 1
    assert safety_conditions[0].result is expected


# ---------------------------------------------------------------------------
# Result templates
# ---------------------------------------------------------------------------


def render_criterion_body(moulinette, criterion):
    template = Template("{% load moulinette %}{% show_criterion_body ep criterion %}")
    return template.render(
        Context({"moulinette": moulinette, "ep": moulinette.ep, "criterion": criterion})
    )


def test_ep_non_ru_categories_render_their_cortege(ep_ru_criteria):
    """The "à vérifier" body lists the species of its own category only."""
    RUConfigHaieFactory()
    setup_per_category_species()

    moulinette = make_moulinette_haie_with_density(
        density=60,
        hedges=make_ru_and_l350_3_hedges(),
        reimplantation="replantation",
    )
    species_9201 = Species.objects.get(cd_ref=9201)

    body = render_criterion_body(moulinette, moulinette.ep.l350_3__ep_regime_unique)
    assert "ce simulateur ne se prononce pas automatiquement" in body
    # The only L350-3 species is "majeur", so the public table stays empty
    assert "Aucune espèce spécifique disponible pour l'affichage" in body
    # ... and the RU species must not leak into the L350-3 body
    assert species_9201.scientific_name not in body


def test_ep_ru_derogation_inventaire_recommends_reducing_the_impact(ep_ru_criteria):
    RUConfigHaieFactory()
    moulinette = make_moulinette_haie_with_density(
        density=40,
        hedges=[make_hedge_factory(length=120)],
        reimplantation="replantation",
    )
    criterion = moulinette.ep.ru__ep_regime_unique
    assert criterion.result_code == "derogation_inventaire"

    body = render_criterion_body(moulinette, criterion)
    assert "un inventaire de terrain est nécessaire" in body
    assert "Pour bénéficier d’une procédure allégée" in body
    assert "en réduisant le linéaire total de haies à détruire" in body
