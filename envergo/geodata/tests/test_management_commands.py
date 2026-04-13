import argparse
import pathlib

import pytest
from django.core.management.base import CommandError
from django.db import connection

from envergo.geodata.management.commands.batch_import_maps import (
    Command as BatchImportCommand,
)
from envergo.geodata.management.commands.copy_geometries_to_prod import (
    ColumnSchema,
    check_no_id_collisions,
    collect_local_map_ids,
    count_existing_prod_maps,
    count_pending_detail_rows,
    detect_geometry_table,
    diff_schemas,
    get_table_columns,
    non_negative_int,
    positive_int,
)
from envergo.geodata.tests.factories import LineFactory, MapFactory, ZoneFactory

pytestmark = pytest.mark.django_db


def write_csv(path: pathlib.Path, header: str, rows: list[str]) -> None:
    """Write a CSV file with the given header and pre-formatted row strings."""
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_batch_import_maps_validation_lists_missing_files(tmp_path):
    """Pre-validation aborts and reports every missing file before import.

    The hint at the end of the error message is what saves the operator from
    importing 1500+ wrong filenames row by row when the data provider ships
    a CSV with a systematic suffix mismatch.
    """
    csv_path = tmp_path / "maps.csv"
    write_csv(
        csv_path,
        "file,name,display_name,description,departments",
        ["does_not_exist.gpkg,Test,Test,desc,44"],
    )

    cmd = BatchImportCommand()
    with pytest.raises(CommandError) as exc_info:
        cmd.load_and_validate_csv(
            csv_path,
            tmp_path,
            default_map_type="terres_emergees",
            default_data_type="certain",
        )

    message = str(exc_info.value)
    assert "does_not_exist.gpkg" in message
    assert "1 missing files" in message
    assert "Hint:" in message


def test_batch_import_maps_uses_csv_columns_and_ignores_extras(tmp_path):
    """CSV map_type/data_type override the defaults; extra columns are ignored."""
    real_file = tmp_path / "real.gpkg"
    real_file.touch()

    csv_path = tmp_path / "maps.csv"
    # The 4 leading columns (statut, code_id, tri_colonne, code_id_carto) are
    # the exact extras present in the Terres_emergées.csv we need to import.
    write_csv(
        csv_path,
        "statut,code_id,tri_colonne,code_id_carto,file,name,display_name,"
        "source,map_type,data_type,description,departments",
        [
            "À déposer,A26,1|A26,A26_0001,real.gpkg,Test,Test display,,"
            'terres_emergees,certain,Some description,"59,62"'
        ],
    )

    cmd = BatchImportCommand()
    rows = cmd.load_and_validate_csv(
        csv_path,
        tmp_path,
        default_map_type=None,
        default_data_type="certain",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.map_type == "terres_emergees"
    assert row.data_type == "certain"
    assert row.name == "Test"
    assert row.display_name == "Test display"
    assert row.departments == ["59", "62"]


def test_batch_import_maps_skips_blank_rows(tmp_path):
    """Trailing or interleaved blank rows are silently tolerated."""
    real_file = tmp_path / "real.gpkg"
    real_file.touch()

    csv_path = tmp_path / "maps.csv"
    write_csv(
        csv_path,
        "file,name,display_name,description,departments",
        [
            "real.gpkg,Test,Test,desc,44",
            ",,,,",  # blank row in the middle
            "",  # truly empty line
        ],
    )

    cmd = BatchImportCommand()
    rows = cmd.load_and_validate_csv(
        csv_path,
        tmp_path,
        default_map_type="terres_emergees",
        default_data_type="certain",
    )

    assert len(rows) == 1


def test_batch_import_maps_flags_row_with_data_but_no_file(tmp_path):
    """A row with content in other columns but no file name is an error."""
    csv_path = tmp_path / "maps.csv"
    write_csv(
        csv_path,
        "file,name,display_name,description,departments",
        [",Test,Test display,desc,44"],
    )

    cmd = BatchImportCommand()
    with pytest.raises(CommandError) as exc_info:
        cmd.load_and_validate_csv(
            csv_path,
            tmp_path,
            default_map_type="terres_emergees",
            default_data_type="certain",
        )

    assert "missing file name" in str(exc_info.value)


def test_batch_import_maps_falls_back_to_default_map_type(tmp_path):
    """When CSV map_type column is empty, --default-map-type fills in."""
    real_file = tmp_path / "real.gpkg"
    real_file.touch()

    csv_path = tmp_path / "maps.csv"
    write_csv(
        csv_path,
        "file,name,display_name,description,departments,map_type,data_type",
        ["real.gpkg,Test,Test,desc,44,,"],
    )

    cmd = BatchImportCommand()
    rows = cmd.load_and_validate_csv(
        csv_path,
        tmp_path,
        default_map_type="zone_humide",
        default_data_type="uncertain",
    )

    assert len(rows) == 1
    assert rows[0].map_type == "zone_humide"
    assert rows[0].data_type == "uncertain"


def test_detect_geometry_table_zone():
    """detect_geometry_table returns 'geodata_zone' for polygon maps."""
    map_obj = MapFactory(map_type="terres_emergees", zones=[])
    ZoneFactory(map=map_obj)
    ZoneFactory(map=map_obj)

    table, count = detect_geometry_table(connection, [map_obj.id])
    assert table == "geodata_zone"
    assert count == 2


def test_detect_geometry_table_line():
    """detect_geometry_table returns 'geodata_line' for line maps."""
    map_obj = MapFactory(map_type="haies", zones=[])
    LineFactory(map=map_obj)

    table, count = detect_geometry_table(connection, [map_obj.id])
    assert table == "geodata_line"
    assert count == 1


def test_detect_geometry_table_raises_on_empty():
    """detect_geometry_table raises if neither table has rows."""
    map_obj = MapFactory(map_type="haies", zones=[])

    with pytest.raises(CommandError, match="no zones and no lines"):
        detect_geometry_table(connection, [map_obj.id])


def test_collect_local_map_ids_filters_by_import_status():
    """Only Maps with import_status='success' are eligible for transfer."""
    success_map = MapFactory(
        map_type="terres_emergees", import_status="success", zones=[]
    )
    MapFactory(map_type="terres_emergees", import_status="failure", zones=[])
    MapFactory(map_type="terres_emergees", import_status=None, zones=[])
    MapFactory(map_type="terres_emergees", import_status="partial_success", zones=[])
    # A different map_type should be ignored entirely.
    MapFactory(map_type="haies", import_status="success", zones=[])

    map_ids, nb_skipped = collect_local_map_ids("terres_emergees")

    assert map_ids == [success_map.id]
    assert nb_skipped == 3


def test_collect_local_map_ids_returns_empty_when_all_skipped():
    """When every local map has non-success status, return ([], total)."""
    MapFactory(map_type="terres_emergees", import_status="failure", zones=[])
    MapFactory(map_type="terres_emergees", import_status=None, zones=[])
    MapFactory(map_type="terres_emergees", import_status="partial_success", zones=[])

    map_ids, nb_skipped = collect_local_map_ids("terres_emergees")

    assert map_ids == []
    assert nb_skipped == 3


def test_count_existing_prod_maps_filters_by_map_type():
    """count_existing_prod_maps only counts rows of the matching map_type.

    Same DB stands in for prod in this test — we only care that the SQL
    filter does what it claims.
    """
    same_type = MapFactory(map_type="terres_emergees", zones=[])
    other_type = MapFactory(map_type="haies", zones=[])
    not_in_batch = MapFactory(map_type="terres_emergees", zones=[])  # noqa: F841

    count = count_existing_prod_maps(
        connection, [same_type.id, other_type.id], "terres_emergees"
    )
    # Only same_type matches: other_type is filtered out by map_type, and
    # not_in_batch is filtered out because its id isn't in the list.
    assert count == 1


def test_count_pending_detail_rows_respects_after_id():
    """count_pending_detail_rows only counts rows above after_id."""
    map_obj = MapFactory(map_type="terres_emergees", zones=[])
    z1 = ZoneFactory(map=map_obj)
    z2 = ZoneFactory(map=map_obj)
    z3 = ZoneFactory(map=map_obj)

    # No after_id: all 3 rows are pending.
    assert count_pending_detail_rows(connection, "geodata_zone", [map_obj.id], 0) == 3

    # After the first id: only the last 2.
    assert (
        count_pending_detail_rows(connection, "geodata_zone", [map_obj.id], z1.id) == 2
    )

    # After the second: only the last 1.
    assert (
        count_pending_detail_rows(connection, "geodata_zone", [map_obj.id], z2.id) == 1
    )

    # After the last: none.
    assert (
        count_pending_detail_rows(connection, "geodata_zone", [map_obj.id], z3.id) == 0
    )


def test_count_pending_detail_rows_rejects_unsafe_table():
    """count_pending_detail_rows interpolates `table` into SQL — guard."""
    with pytest.raises(CommandError, match="Refusing to operate"):
        count_pending_detail_rows(connection, "geodata_map", [1], 0)


def test_get_table_columns_raises_on_unknown_table():
    """An unknown table name produces a clear error rather than silent ''."""
    with pytest.raises(CommandError, match="not found"):
        get_table_columns(connection, "this_table_does_not_exist")


def test_positive_int_validator():
    """positive_int rejects zero, negatives, and non-numeric input."""
    assert positive_int("1") == 1
    assert positive_int("5000") == 5000

    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("-1")
    # Non-numeric input must produce the custom error, not a bare ValueError.
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("abc")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("1.5")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("")


def test_non_negative_int_validator():
    """non_negative_int accepts zero, rejects negatives and non-numeric input."""
    assert non_negative_int("0") == 0
    assert non_negative_int("42") == 42

    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("-1")
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("abc")
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("1.5")
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("")


# ── diff_schemas (schema drift comparison) ────────────────────────────


def col(name, data_type="integer", is_nullable="NO"):
    """Tiny factory for ColumnSchema in tests."""
    return ColumnSchema(name=name, data_type=data_type, is_nullable=is_nullable)


def test_diff_schemas_identical_returns_none():
    """Two identical schemas are equivalent."""
    schema = [
        col("id"),
        col("name", "character varying"),
        col("created_at", "timestamp with time zone"),
    ]
    assert diff_schemas(schema, schema) is None


def test_diff_schemas_same_columns_different_order_returns_none():
    """Different physical column order is equivalent.

    This is the real-world case where prod was built incrementally and
    local was built from squashed migrations: same logical schema, on
    disk in different order. Our COPY uses an explicit column list, so
    physical order is irrelevant.
    """
    local = [
        col("id"),
        col("name", "character varying"),
        col("file", "character varying"),
        col("created_at", "timestamp with time zone"),
    ]
    prod = [
        col("file", "character varying"),
        col("created_at", "timestamp with time zone"),
        col("id"),
        col("name", "character varying"),
    ]
    assert diff_schemas(local, prod) is None


def test_diff_schemas_missing_column_on_prod():
    """A column present on local but not on prod is flagged."""
    local = [col("id"), col("name", "character varying"), col("new_field")]
    prod = [col("id"), col("name", "character varying")]

    diff = diff_schemas(local, prod)
    assert diff is not None
    assert "only on local" in diff
    assert "new_field" in diff


def test_diff_schemas_extra_column_on_prod():
    """A column present on prod but not on local is flagged."""
    local = [col("id"), col("name", "character varying")]
    prod = [col("id"), col("name", "character varying"), col("legacy_field")]

    diff = diff_schemas(local, prod)
    assert diff is not None
    assert "only on prod" in diff
    assert "legacy_field" in diff


def test_diff_schemas_type_mismatch():
    """Same column name, different data_type is flagged."""
    local = [col("id"), col("area", data_type="integer")]
    prod = [col("id"), col("area", data_type="bigint")]

    diff = diff_schemas(local, prod)
    assert diff is not None
    assert "'area'" in diff
    assert "integer" in diff
    assert "bigint" in diff


def test_diff_schemas_nullability_mismatch():
    """Same column name and type, different nullability is flagged."""
    local = [col("id"), col("name", "character varying", is_nullable="NO")]
    prod = [col("id"), col("name", "character varying", is_nullable="YES")]

    diff = diff_schemas(local, prod)
    assert diff is not None
    assert "'name'" in diff
    assert "nullable=NO" in diff
    assert "nullable=YES" in diff


# ── check_no_id_collisions: empty and NULL map_type ────────────────


def test_check_no_id_collisions_flags_empty_map_type():
    """A prod row with empty-string map_type is treated as a collision.

    Empty `map_type` is allowed by the model (`blank=True`) and exists in
    the real prod database for legacy untyped maps. If one of those rows
    happens to share an id with a local batch we're about to push, the
    script must abort — even though the destructive code paths would
    silently skip empty-type rows because of their map_type filter, the
    PK collision on COPY would still fail. Better to flag it loudly.
    """
    legacy = MapFactory(map_type="", zones=[])

    with pytest.raises(CommandError, match="Id collision detected"):
        check_no_id_collisions(connection, [legacy.id], "terres_emergees")


def test_check_no_id_collisions_returns_clean_on_matching_type():
    """A prod row of the *same* map_type is NOT flagged as a collision.

    Same id + same map_type is the intended overwrite case (counted by
    count_existing_prod_maps and surfaced separately in the banner).
    """
    same_type = MapFactory(map_type="terres_emergees", zones=[])

    # Should return cleanly (no exception).
    check_no_id_collisions(connection, [same_type.id], "terres_emergees")
