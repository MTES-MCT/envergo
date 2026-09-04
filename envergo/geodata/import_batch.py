"""Parsing and validation of map import batch CSV files.

Pure functions only: no db access, no storage access. The orchestration
task (`process_map_import_batch`) is responsible for matching rows against
uploaded files and existing Map objects.

CSV conventions follow the `batch_import_maps` management command:
utf-8-sig encoding, unknown columns ignored, blank rows skipped,
departments comma-separated inside a single (quoted) cell.
"""

from dataclasses import dataclass, field

from envergo.geodata.management.helpers import VALID_DATA_TYPES, VALID_MAP_TYPES

REQUIRED_COLUMNS = ("reference", "name", "description", "departments")
OPTIONAL_COLUMNS = (
    "file",
    "display_name",
    "source",
    "map_type",
    "data_type",
    "display_for_user",
)

TRUE_VALUES = {"true", "1", "oui", "vrai"}
FALSE_VALUES = {"false", "0", "non", "faux"}

REFERENCE_MAX_LENGTH = 128


@dataclass(frozen=True)
class ParsedBatchRow:
    """A normalised, validated CSV row ready to create or update a Map.

    Optional columns hold an empty string (or None for booleans) when the
    cell is blank, meaning "keep the existing value" on update.

    `file` is optional: a blank cell means "carte existante, mise à jour des
    métadonnées seule", i.e. update the Map's fields without re-importing its
    geometry. Such a row can only target an already existing map (a file is
    required to create one).

    `departments` is the exception among the required columns: an empty
    list is a legitimate value (a map covering the whole country has no
    department), so a blank cell means "aucun département" and clears the
    field on update. Every other required column rejects a blank cell.
    """

    reference: str
    file: str
    name: str
    description: str
    display_name: str = ""
    source: str = ""
    map_type: str = ""
    data_type: str = ""
    display_for_user: bool | None = None
    departments: list = field(default_factory=list)


def is_blank_row(raw_row):
    """True when every column in the row is empty or whitespace.

    Trailing newlines and visual separators in CSVs exported from
    spreadsheet software produce rows like this. They carry no payload and
    should be silently skipped; a row with *some* content and missing
    required values is an operator mistake and must be flagged.
    """
    return not any((value or "").strip() for value in raw_row.values())


def validate_headers(fieldnames):
    """Return the list of missing required columns error messages.

    A non-empty result is batch-fatal: no row can be processed reliably
    when a required column is absent.
    """
    fieldnames = fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        return [f"Colonnes manquantes dans le CSV : {', '.join(missing)}"]
    return []


def find_missing_files(reader, uploaded_names):
    """Return {file_name: nb_rows} for files referenced but not uploaded."""
    missing = {}
    seen_references = set()
    for line_no, raw_row in enumerate(reader, start=2):
        if is_blank_row(raw_row):
            continue
        result, errors = parse_batch_row(line_no, raw_row)
        if errors:
            continue
        if result.reference in seen_references:
            continue
        seen_references.add(result.reference)
        if not result.file:
            continue
        if result.file not in uploaded_names:
            missing[result.file] = missing.get(result.file, 0) + 1
    return missing


def parse_batch_row(line_no, raw_row):
    """Normalize and validate a single non-blank raw CSV row.

    Returns (ParsedBatchRow, []) on success or (None, [error_string]) on
    failure. The caller is responsible for skipping blank rows (via
    is_blank_row) and for checks requiring db or storage access (duplicate
    reference, uploaded file existence).
    """
    reference = (raw_row.get("reference") or "").strip()
    if not reference:
        return None, [f"ligne {line_no} : référence manquante"]
    if len(reference) > REFERENCE_MAX_LENGTH:
        return None, [
            f"ligne {line_no} : référence trop longue "
            f"(max {REFERENCE_MAX_LENGTH} caractères)"
        ]

    # A blank file cell is legitimate: it flags a metadata-only update of an
    # existing map, so its geometry is never re-imported (see ParsedBatchRow).
    file_name = (raw_row.get("file") or "").strip()

    name = (raw_row.get("name") or "").strip()
    if not name:
        return None, [f"ligne {line_no} : nom de carte manquant"]

    # The model requires a description, and required columns overwrite on
    # update: accepting a blank cell here would silently erase the
    # description of an existing map.
    description = (raw_row.get("description") or "").strip()
    if not description:
        return None, [f"ligne {line_no} : description manquante"]

    map_type = (raw_row.get("map_type") or "").strip()
    if map_type and map_type not in VALID_MAP_TYPES:
        return None, [f"ligne {line_no} : map_type inconnu {map_type!r}"]

    data_type = (raw_row.get("data_type") or "").strip()
    if data_type and data_type not in VALID_DATA_TYPES:
        return None, [f"ligne {line_no} : data_type inconnu {data_type!r}"]

    display_for_user = None
    raw_display = (raw_row.get("display_for_user") or "").strip().lower()
    if raw_display:
        if raw_display in TRUE_VALUES:
            display_for_user = True
        elif raw_display in FALSE_VALUES:
            display_for_user = False
        else:
            return None, [
                f"ligne {line_no} : display_for_user invalide {raw_display!r}"
            ]

    return (
        ParsedBatchRow(
            reference=reference,
            file=file_name,
            name=name,
            description=description,
            display_name=(raw_row.get("display_name") or "").strip(),
            source=(raw_row.get("source") or "").strip(),
            map_type=map_type,
            data_type=data_type,
            display_for_user=display_for_user,
            departments=[
                d.strip()
                for d in (raw_row.get("departments") or "").split(",")
                if d.strip()
            ],
        ),
        [],
    )
