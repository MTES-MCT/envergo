"""Bulk-import a series of map files described in a CSV.

Designed to push large batches of maps that don't fit in a single Scalingo
one-off container session. Pair with `process_pending_maps` to schedule the
async processing of every imported file, and `copy_geometries_to_prod` to
push the resulting Zone/Line rows to production.
"""

import csv
import pathlib
import sys
from dataclasses import dataclass, field
from logging import getLogger

from django.core.files import File as DjangoFile
from django.core.management.base import BaseCommand, CommandError

from envergo.geodata.management.helpers import (
    VALID_DATA_TYPES,
    VALID_MAP_TYPES,
    get_default_db_identity,
    refuse_production_settings,
)
from envergo.geodata.models import DATA_TYPES, Map
from envergo.geodata.utils import count_features

logger = getLogger(__name__)


REQUIRED_CSV_COLUMNS = ("file", "name", "display_name", "description", "departments")
OPTIONAL_CSV_COLUMNS = ("map_type", "data_type", "source")


@dataclass(frozen=True)
class ParsedRow:
    """A normalised, validated CSV row ready to become a Map."""

    file: str
    name: str
    display_name: str
    description: str
    source: str
    map_type: str
    data_type: str
    departments: list = field(default_factory=list)


def is_blank_row(raw_row):
    """True when every column in the row is empty or whitespace.

    Trailing newlines and visual separators in CSVs exported from
    spreadsheet software produce rows like this. They carry no payload
    and should be silently skipped, but a row with *some* content and an
    empty `file` column is an operator mistake and must be flagged.
    """
    return not any((value or "").strip() for value in raw_row.values())


def parse_row(line_no, raw_row, default_map_type, default_data_type):
    """Normalise and validate a single non-blank raw CSV row.

    Returns either a ParsedRow on success or an error string
    ('line N: ...') if the row has a missing file name, an unknown
    map_type, or an unknown data_type. The caller is responsible for
    skipping blank rows (via is_blank_row) before calling this.

    Filesystem checks (does the referenced file exist?) live in the
    caller because they need the data_dir.
    """
    file_name = (raw_row.get("file") or "").strip()
    if not file_name:
        return f"line {line_no}: missing file name"

    name = (raw_row.get("name") or "").strip()
    display_name = (raw_row.get("display_name") or "").strip() or name
    map_type = (raw_row.get("map_type") or "").strip() or default_map_type
    data_type = (raw_row.get("data_type") or "").strip() or default_data_type

    if map_type not in VALID_MAP_TYPES:
        return f"line {line_no}: unknown map_type {map_type!r}"
    if data_type not in VALID_DATA_TYPES:
        return f"line {line_no}: unknown data_type {data_type!r}"

    return ParsedRow(
        file=file_name,
        name=name,
        display_name=display_name,
        description=raw_row.get("description") or "",
        source=(raw_row.get("source") or "").strip(),
        map_type=map_type,
        data_type=data_type,
        departments=[
            d.strip()
            for d in (raw_row.get("departments") or "").split(",")
            if d.strip()
        ],
    )


class Command(BaseCommand):
    help = """Upload a series of maps listed in a CSV file.

    Required CSV columns:
        file, name, display_name, description, departments

    Optional CSV columns (override the --default-* flags):
        map_type, data_type, source

    Any other columns are ignored.
    """

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=pathlib.Path)
        parser.add_argument("data_dir", type=pathlib.Path)
        parser.add_argument(
            "--default-map-type",
            choices=sorted(VALID_MAP_TYPES),
            help="map_type to use when the CSV row has no map_type column or "
            "the column is empty",
        )
        parser.add_argument(
            "--default-data-type",
            choices=sorted(VALID_DATA_TYPES),
            default=DATA_TYPES.certain,
            help="data_type to use when the CSV row has no data_type column "
            "or the column is empty (default: certain)",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Delete every existing Map matching --purge-map-type before "
            "importing. Requires interactive confirmation.",
        )
        parser.add_argument(
            "--purge-map-type",
            help="map_type filter for --purge (defaults to --default-map-type)",
        )

    def handle(self, *args, **options):
        """Validate the CSV, optionally purge existing maps, then import each row.

        Refuses to run with a production-flavoured settings module before
        any work happens. The validation pass aborts cleanly on any
        missing file or invalid map_type / data_type so a partial import
        can never leave half-created Map rows pointing at the wrong files.
        """
        refuse_production_settings()

        csv_path = options["csv_file"]
        dir_path = options["data_dir"]

        rows = self.load_and_validate_csv(
            csv_path,
            dir_path,
            options["default_map_type"],
            options["default_data_type"],
        )
        self.stdout.write(f"Validated {len(rows)} rows. All referenced files exist.")

        if options["purge"]:
            purge_type = options["purge_map_type"] or options["default_map_type"]
            if not purge_type:
                raise CommandError(
                    "--purge requires --purge-map-type or --default-map-type"
                )
            self.purge(purge_type)

        self.stdout.write(f"Importing maps into {get_default_db_identity()}.")
        for row in rows:
            self.import_row(row, dir_path)

    def load_and_validate_csv(
        self, csv_path, dir_path, default_map_type, default_data_type
    ):
        """Read the CSV, normalise every row, and verify all files exist.

        Returns a list of ParsedRow ready for import. Raises CommandError
        listing every problem if any row references a missing file or has
        an invalid map_type/data_type. Failing loudly here is intentional:
        a partial import would leave Map rows pointing at the wrong files
        and require manual cleanup.
        """
        rows: list[ParsedRow] = []
        missing_files: list[str] = []
        invalid_rows: list[str] = []

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            # Header is line 1, so the first data row is line 2.
            for line_no, raw_row in enumerate(reader, start=2):
                if is_blank_row(raw_row):
                    continue

                result = parse_row(
                    line_no, raw_row, default_map_type, default_data_type
                )
                if isinstance(result, str):
                    invalid_rows.append(result)
                    continue

                full_path = dir_path / result.file
                if not full_path.exists():
                    missing_files.append(f"line {line_no}: {full_path}")
                    continue

                rows.append(result)

        if missing_files or invalid_rows:
            details = "\n  ".join(missing_files + invalid_rows)
            raise CommandError(
                f"""\
CSV validation failed ({len(missing_files)} missing files, {len(invalid_rows)} invalid rows):
  {details}

Hint: if every filename is missing the same suffix, you can fix the CSV
with a sed one-liner that targets the file column (whichever position it
sits at), e.g.:
    sed -i 's/,\\([^,]*\\)\\.gpkg,/,\\1_.gpkg,/' "{csv_path}"\
"""
            )

        return rows

    def purge(self, map_type):
        """Delete every Map of the given type from the configured database.

        Always interactive — there is no flag to skip the confirmation,
        because the purge cascades through every model whose foreign key
        to Map declares ON DELETE CASCADE (geodata_zone, geodata_line,
        hedges_speciesmap, ...). The destination database is shown in
        the prompt so a wrong-terminal mistake is hard to miss.
        """
        qs = Map.objects.filter(map_type=map_type)
        count = qs.count()
        self.stdout.write(
            self.style.WARNING(
                f"This will DELETE {count} existing maps of type "
                f"{map_type!r} from {get_default_db_identity()}.\n"
                f"Cascading deletes will also remove every dependent row "
                f"in geodata_zone, geodata_line, hedges_speciesmap, etc."
            )
        )
        confirm = input("Type 'yes' to continue: ").strip()
        if confirm != "yes":
            self.stdout.write("Operation cancelled.")
            sys.exit(0)
        self.stdout.write(f"Purging {count} maps of type {map_type!r}.")
        qs.delete()

    def import_row(self, row, dir_path):
        full_path = dir_path / row.file
        with open(full_path, "rb") as f:
            map_file = DjangoFile(f)
            map_obj = Map.objects.create(
                name=row.name,
                display_name=row.display_name,
                description=row.description,
                source=row.source,
                # Empty list trips the ArrayField constraint in some
                # configurations; the field is nullable, so prefer None.
                departments=row.departments or None,
                map_type=row.map_type,
                data_type=row.data_type,
                expected_geometries=count_features(map_file),
            )
            self.stdout.write(f"Importing {row.file} as {row.map_type}/{row.data_type}")
            map_obj.file.save(row.file, map_file)
