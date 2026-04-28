import csv
import io
import logging
import os

import requests
from django.db import IntegrityError
from django.utils import timezone

from config.celery_app import app
from envergo.hedges.models import (
    HEDGE_PROPERTIES,
    IMPORT_STATUSES,
    LEVELS_OF_CONCERN,
    HedgeTypeFactory,
    Species,
    SpeciesMap,
    SpeciesMapFile,
)
from envergo.hedges.species_stubs import (
    make_stub_common_name,
    make_stub_scientific_name,
)

logger = logging.getLogger(__name__)


ALL_HEDGE_PROPERTIES = dict(HEDGE_PROPERTIES).keys()


@app.task(bind=True)
def process_species_map_file(task, object_id):
    """Process a single SpeciesMapFile objects.

    This scripts import the file data and associates Species with Maps.
    """
    logger.info(f"Starting import on species map file {object_id}")

    smf = SpeciesMapFile.objects.get(pk=object_id)
    import_log = []

    # Store the task data in the model, so we can display progression
    # in the admin page.
    smf.task_id = task.request.id
    smf.import_log = ""
    smf.import_status = None
    smf.save()

    # Clear existing data
    logger.info("Clearing existing data")
    SpeciesMap.objects.filter(species_map_file=smf).delete()

    # Process csv file
    logger.info("Processing csv file")
    species_maps = []
    with extract_file(smf.file) as csvfile:
        nb_lines = 0
        reader = csv.DictReader(csvfile)
        for row in reader:
            nb_lines += 1

            try:
                species_map = process_species_file_map_row(row, smf)
                species_maps.append(species_map)
            except Species.DoesNotExist:
                if "common_name" in row:
                    msg = f"Espèce inconnue {row['common_name']}"
                else:
                    msg = f"Espèce inconnue à la ligne {nb_lines + 1}"
                import_log.append(msg)
                logger.warning(msg)
            except (ValueError, TypeError, KeyError, IntegrityError) as e:
                msg = f"Erreur d'import sur la ligne {nb_lines + 1}: {e}"
                import_log.append(msg)
                logger.error(msg)

    # Create objects with a single query
    logger.info("Saving data objects")
    objects = SpeciesMap.objects.bulk_create(species_maps)

    # Update the import status and metadata
    if len(objects) == nb_lines:
        smf.import_status = IMPORT_STATUSES.success
    elif len(objects) > 0:
        smf.import_status = IMPORT_STATUSES.partial_success
    else:
        smf.import_status = IMPORT_STATUSES.failure

    smf.task_id = None
    smf.import_date = timezone.now()
    smf.import_log = "\n".join(import_log)
    smf.save()
    logger.info("Import finished")


def extract_file(field_file):
    """Handle local and remote files."""

    if field_file.url.startswith("http"):
        r = requests.get(field_file.url, stream=True)
        # utf-8-sig to remove the eventual bom
        content = io.StringIO(r.content.decode("utf-8-sig"))
        return content

    elif os.path.exists(field_file.path):
        with open(field_file.path, "rb") as f:
            raw = f.read()
        return io.StringIO(raw.decode("utf-8-sig"))

    else:
        raise RuntimeError("File not found")


def process_species_file_map_row(row, smf):
    """Process a single CSV row, creating a SpeciesMap.

    Supports three species identification methods (tried in order):
    CD_REF (RU format), CD_NOM (legacy), common_name (legacy).
    When CD_REF is used and the species doesn't exist, a stub is created.
    """
    species = find_or_create_species(row)

    hedge_types = []
    for hedge_type in HedgeTypeFactory.build_from_context(
        single_procedure=False
    ).values:
        if row.get(hedge_type, "").strip().upper() in ("TRUE", "1"):
            hedge_types.append(hedge_type)

    hedge_properties = []
    for hedge_property in ALL_HEDGE_PROPERTIES:
        if row.get(hedge_property, "").strip().upper() in ("TRUE", "1"):
            hedge_properties.append(hedge_property)

    local_level = parse_level_of_concern(row.get("level_of_concern", ""))

    return SpeciesMap(
        species=species,
        map=smf.map,
        species_map_file=smf,
        hedge_types=hedge_types,
        hedge_properties=hedge_properties,
        level_of_concern=local_level,
    )


def find_or_create_species(row):
    """Look up a Species from a CSV row, creating a stub if needed.

    Identification precedence: CD_REF (RU format) → CD_NOM (legacy) →
    common_name (legacy). For CD_REF, missing species are auto-created
    with placeholder names that import_taxref will later enrich.
    """
    if "CD_REF" in row and row["CD_REF"]:
        cd_ref = int(row["CD_REF"])
        try:
            species, _ = Species.objects.get_or_create(
                cd_ref=cd_ref,
                defaults={
                    "scientific_name": make_stub_scientific_name(cd_ref),
                    "common_name": make_stub_common_name(cd_ref),
                },
            )
        except IntegrityError:
            species = Species.objects.get(cd_ref=cd_ref)
    elif "CD_NOM" in row:
        cd_nom = int(row["CD_NOM"])
        species = Species.objects.get(taxref_ids__contains=[cd_nom])
    elif "common_name" in row:
        species = Species.objects.get(common_name=row["common_name"])
    else:
        raise ValueError(
            "CSV row has no species identifier (CD_REF, CD_NOM, or common_name)"
        )

    return species


# Reverse mapping from display labels ("Majeur", "Très fort"…) to database
# values ("majeur", "tres_fort"…), used to normalize CSV import data.
LEVEL_OF_CONCERN_DISPLAY_TO_DB = {label: value for value, label in LEVELS_OF_CONCERN}


def parse_level_of_concern(raw_value):
    """Convert a display-format level_of_concern to its database value."""

    stripped = raw_value.strip()
    if not stripped:
        return None
    db_value = LEVEL_OF_CONCERN_DISPLAY_TO_DB.get(stripped)
    if db_value is None:
        logger.warning("Unknown level_of_concern value: %s", stripped)
    return db_value
