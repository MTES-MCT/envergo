"""Parsing and validation of map import batch CSV files.

Pure functions only: no db access, no storage access. The orchestration
task (`process_map_import_batch`) is responsible for matching rows against
uploaded files and existing Map objects.

CSV conventions follow the `batch_import_maps` management command:
utf-8-sig encoding, unknown columns ignored, blank rows skipped,
departments comma-separated inside a single (quoted) cell.
"""

import csv
from dataclasses import dataclass, field

from envergo.geodata.management.helpers import VALID_DATA_TYPES, VALID_MAP_TYPES
from envergo.geodata.models import Map
from envergo.geodata.utils import read_csv_file

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
    """A normalized, validated CSV row ready to create or update a Map.

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


def is_file_valid(csv_file, batch_files=None, check_files=True) -> list[str]:
    """Checks if a CSV file is valid, and concatenate errors of each row if not.

    `check_files` selects the validation scope:
    - True: the batch is complete, so the CSV is validated together with its
      uploaded files (`batch_files`). Every referenced file must have been
      uploaded.
    - False: only the CSV content is validated, before any file is uploaded.
      Referenced files are not looked up, so `batch_files` can be omitted.

    In both cases, rows without a file must target an existing map.
    """
    uploaded_files = {f.name for f in batch_files.all()} if batch_files else set()
    reader = csv.DictReader(read_csv_file(csv_file))
    seen_references = set()
    needed_files = []
    errors = []
    errors.extend(validate_headers(reader.fieldnames))
    for raw_row in reader:
        # Not enumerate(): the csv module skips empty lines, which would shift
        # the reported line numbers.
        line_number = reader.line_num
        if is_blank_row(raw_row):
            continue
        result, row_errors = parse_batch_row(line_number, raw_row)
        if row_errors:
            errors.extend(row_errors)
            continue
        if result.reference in seen_references:
            errors.append(
                f"Ligne {line_number} : référence en double  : '{result.reference}'."
            )
        seen_references.add(result.reference)
        if not result.file:
            needed_files.append((result.reference, line_number))
        elif check_files and result.file not in uploaded_files:
            errors.append(
                f"Ligne {line_number} : fichier référencé non téléversé : {result.file}."
            )

    if needed_files:
        needed_refs = {reference for reference, line_number in needed_files}
        existing = set(
            Map.objects.filter(reference__in=needed_refs).values_list(
                "reference", flat=True
            )
        )
        for reference, line_number in needed_files:
            if reference not in existing:
                errors.append(
                    f"Ligne {line_number} : fichier manquant pour une carte inexistante : '{reference}'."
                )

    return errors


def is_line_valid(
    line_number, raw_row, batch_files
) -> tuple[ParsedBatchRow | None, list[str]]:
    """Checks if a single CSV line is valid."""
    errors = []
    if is_blank_row(raw_row):
        return None, errors
    result, row_errors = parse_batch_row(line_number, raw_row)
    if row_errors:
        errors.extend(row_errors)
        return None, errors
    if not result.file:
        if not Map.objects.filter(reference=result.reference).exists():
            errors.append(
                f"Fichier manquant pour une carte inexistante : '{result.reference}' — ligne {line_number}."
            )
    elif not batch_files.filter(name=result.file).exists():
        errors.append(
            f"Fichier référencé non téléversé : {result.file} — ligne {line_number}."
        )
    return result, errors


def is_blank_row(raw_row):
    """True when every column in the row is empty or whitespace."""
    return not any((value or "").strip() for value in raw_row.values())


def validate_headers(fieldnames):
    """Return the list of missing required columns error messages."""
    fieldnames = fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        return [f"Colonnes manquantes dans le CSV : {', '.join(missing)}"]
    return []


def parse_batch_row(line_number, raw_row):
    """Normalize and validate a single non-blank raw CSV row.

    Returns (ParsedBatchRow, []) on success or (None, [error_string]) on
    failure.
    """
    reference = (raw_row.get("reference") or "").strip()
    if not reference:
        return None, [f"Ligne {line_number} : référence manquante."]
    if len(reference) > REFERENCE_MAX_LENGTH:
        return None, [
            f"Ligne {line_number} : référence trop longue "
            f"(max {REFERENCE_MAX_LENGTH} caractères)."
        ]

    # A blank file cell is legitimate: it flags a metadata-only update of an
    # existing map, so its geometry is never re-imported (see ParsedBatchRow).
    file_name = (raw_row.get("file") or "").strip()

    name = (raw_row.get("name") or "").strip()
    if not name:
        return None, [f"Ligne {line_number} : nom de carte manquant."]

    # The model requires a description, and required columns overwrite on
    # update: accepting a blank cell here would silently erase the
    # description of an existing map.
    description = (raw_row.get("description") or "").strip()
    if not description:
        return None, [f"Ligne {line_number} : description manquante."]

    map_type = (raw_row.get("map_type") or "").strip()
    if map_type and map_type not in VALID_MAP_TYPES:
        return None, [f"Ligne {line_number} : map_type inconnu {map_type!r}."]

    data_type = (raw_row.get("data_type") or "").strip()
    if data_type and data_type not in VALID_DATA_TYPES:
        return None, [f"Ligne {line_number} : data_type inconnu {data_type!r}."]

    display_for_user = None
    raw_display = (raw_row.get("display_for_user") or "").strip().lower()
    if raw_display:
        if raw_display in TRUE_VALUES:
            display_for_user = True
        elif raw_display in FALSE_VALUES:
            display_for_user = False
        else:
            return None, [
                f"Ligne {line_number} : display_for_user invalide {raw_display!r}."
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
