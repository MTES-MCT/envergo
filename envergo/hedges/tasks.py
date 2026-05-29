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
    SpeciesHabitat,
    SpeciesHabitatFile,
)
from envergo.hedges.species_stubs import make_stub_scientific_name

logger = logging.getLogger(__name__)


ALL_HEDGE_PROPERTIES = dict(HEDGE_PROPERTIES).keys()


@app.task(bind=True)
def process_species_habitat_file(task, object_id):
    """Process a single SpeciesHabitatFile.

    Imports the file data and associates Species with Maps via SpeciesHabitat.
    """
    logger.info(f"Starting import on species habitat file {object_id}")

    habitat_file = SpeciesHabitatFile.objects.get(pk=object_id)
    import_log = []

    # Store the task data in the model, so we can display progression
    # in the admin page.
    habitat_file.task_id = task.request.id
    habitat_file.import_log = ""
    habitat_file.import_status = None
    habitat_file.save()

    # Clear existing data
    logger.info("Clearing existing data")
    SpeciesHabitat.objects.filter(species_habitat_file=habitat_file).delete()

    # Process csv file
    logger.info("Processing csv file")
    habitats = []
    species_to_update = {}
    with extract_file(habitat_file.file) as csvfile:
        nb_lines = 0
        reader = csv.DictReader(csvfile)
        for row in reader:
            nb_lines += 1

            try:
                habitat, modified_species = process_species_habitat_row(
                    row, habitat_file, import_log
                )
                habitats.append(habitat)
                if modified_species is not None:
                    species_to_update[modified_species.pk] = modified_species
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

    # Batch-save species and habitat changes
    logger.info("Saving data objects")
    if species_to_update:
        Species.objects.bulk_update(species_to_update.values(), ["adhoc_group"])
    objects = SpeciesHabitat.objects.bulk_create(habitats)

    # Update the import status and metadata
    if len(objects) == nb_lines:
        habitat_file.import_status = IMPORT_STATUSES.success
    elif len(objects) > 0:
        habitat_file.import_status = IMPORT_STATUSES.partial_success
    else:
        habitat_file.import_status = IMPORT_STATUSES.failure

    habitat_file.task_id = None
    habitat_file.import_date = timezone.now()
    habitat_file.import_log = "\n".join(import_log)
    habitat_file.save()
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


def process_species_habitat_row(row, habitat_file, import_log=None):
    """Process a single CSV row, creating a SpeciesHabitat.

    Supports three species identification methods (tried in order):
    CD_REF (RU format), CD_NOM (legacy), common_name (legacy).
    When CD_REF is used and the species doesn't exist, a stub is created.

    Returns (habitat, modified_species) where modified_species is the Species
    instance if its adhoc_group was updated in-memory, or None otherwise.
    The caller is responsible for persisting the change via bulk_update.
    """
    species = find_or_create_species(row)
    modified_species = update_species_adhoc_group(species, row)

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

    local_level = parse_level_of_concern(row.get("level_of_concern", ""), import_log)

    habitat = SpeciesHabitat(
        species=species,
        map=habitat_file.map,
        species_habitat_file=habitat_file,
        hedge_types=hedge_types,
        hedge_properties=hedge_properties,
        level_of_concern=local_level,
    )
    return habitat, modified_species


def find_or_create_species(row):
    """Look up a Species from a CSV row, creating a stub if needed.

    Missing species are auto-created with a placeholder scientific_name that
    import_taxref will later enrich.
    """
    if "CD_REF" in row and row["CD_REF"]:
        cd_ref = int(row["CD_REF"])
        species, _ = Species.objects.get_or_create(
            cd_ref=cd_ref,
            defaults={
                "scientific_name": make_stub_scientific_name(cd_ref),
            },
        )
    elif "CD_NOM" in row:
        cd_nom = int(row["CD_NOM"])
        species = Species.objects.get(cd_noms__contains=[cd_nom])
    elif "common_name" in row:
        species = Species.objects.get(common_name=row["common_name"])
    else:
        raise ValueError(
            "CSV row has no species identifier (CD_REF, CD_NOM, or common_name)"
        )

    return species


def update_species_adhoc_group(species, row):
    """Set species.adhoc_group from the CSV 'groupe' column if present.

    Mutates the species in-memory but does not save. Returns the species
    if modified, None otherwise. The caller batches saves via bulk_update.
    """
    raw_group = row.get("groupe", "").strip()
    if not raw_group:
        return None

    if species.adhoc_group == raw_group:
        return None

    species.adhoc_group = raw_group
    return species


# Reverse mapping from display labels ("Majeur", "Très fort"…) to database
# values ("majeur", "tres_fort"…), used to normalize CSV import data.
# Keys are lowercased so the lookup is case-insensitive.
LEVEL_OF_CONCERN_DISPLAY_TO_DB = {
    label.lower(): value for value, label in LEVELS_OF_CONCERN
}


def parse_level_of_concern(raw_value, import_log=None):
    """Convert a display-format level_of_concern to its database value."""

    stripped = raw_value.strip()
    if not stripped:
        return None
    db_value = LEVEL_OF_CONCERN_DISPLAY_TO_DB.get(stripped.lower())
    if db_value is None:
        msg = f"Niveau d'enjeu inconnu : « {stripped} »"
        logger.warning(msg)
        if import_log is not None:
            import_log.append(msg)
    return db_value
