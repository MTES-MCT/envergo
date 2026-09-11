"""The catalog as seen by a criterion evaluator.

Evaluators read their own data first, then the shared moulinette catalog, and
never write into the shared one.
"""

from collections import ChainMap

from envergo.moulinette.models import MoulinetteCatalog


def make_catalogs():
    shared = MoulinetteCatalog({"motif": "securite", "lineaire_total": 1000})
    own = {}
    return own, shared, ChainMap(own, shared)


def test_reads_fall_through_to_the_shared_catalog():
    own, shared, catalog = make_catalogs()

    assert catalog["motif"] == "securite"
    assert "motif" in catalog
    assert catalog.get("motif") == "securite"


def test_own_data_shadows_the_shared_catalog():
    own, shared, catalog = make_catalogs()
    own["lineaire_total"] = 42

    assert catalog["lineaire_total"] == 42
    assert shared["lineaire_total"] == 1000


def test_writes_stay_in_the_evaluator_data():
    own, shared, catalog = make_catalogs()

    catalog["geoportail_url"] = "https://ru"
    catalog.update({"density_400": 12.5})

    assert own == {"geoportail_url": "https://ru", "density_400": 12.5}
    assert "geoportail_url" not in shared
    assert "density_400" not in shared


def test_get_returns_the_default_for_a_missing_key():
    own, shared, catalog = make_catalogs()

    assert catalog.get("unknown") is None
    assert catalog.get("unknown", "fallback") == "fallback"


def test_flattening_merges_both_layers():
    own, shared, catalog = make_catalogs()
    own["lineaire_total"] = 42
    own["geoportail_url"] = "https://ru"

    assert dict(catalog) == {
        "motif": "securite",
        "lineaire_total": 42,
        "geoportail_url": "https://ru",
    }
