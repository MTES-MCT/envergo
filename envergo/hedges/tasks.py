import csv
import logging

from django.utils import timezone

from config.celery_app import app
from envergo.hedges.models import (
    HEDGE_PROPERTIES,
    HEDGE_TYPES,
    IMPORT_STATUSES,
    Species,
    SpeciesMap,
    SpeciesMapFile,
)

logger = logging.getLogger(__name__)


ALL_HEDGE_TYPES = dict(HEDGE_TYPES).keys()
ALL_HEDGE_PROPERTIES = dict(HEDGE_PROPERTIES).keys()


@app.task(bind=True)
def process_species_map_file(task, object_id):
    """Process a single SpeciesMapFile objects.

    This scripts import the file data and associatets Species with Maps.
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
    with open(smf.file.path, "r") as csvfile:
        nb_lines = 0
        reader = csv.DictReader(csvfile)
        for row in reader:
            nb_lines += 1

            try:
                species_map = process_species_file_map_row(row, smf)
                species_maps.append(species_map)
            except Species.DoesNotExist:
                if "common_name" in row:
                    msg = f"Espèce inconnue {row["common_name"]}"
                else:
                    msg = f"Espèce inconnue à la ligne {nb_lines + 1}"
                import_log.append(msg)
                logger.warning(msg)
            except Exception as e:
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


def process_species_file_map_row(row, smf):
    """Process a single file row."""
    if "CD_NOM" in row:
        species_taxref_id = row["CD_NOM"]
        species = Species.objects.get(taxref_ids__contains=[species_taxref_id])
    else:
        species = Species.objects.get(common_name=row["common_name"])

    hedge_types = []
    for hedge_type in ALL_HEDGE_TYPES:
        if bool(row[hedge_type]):
            hedge_types.append(hedge_type)

    hedge_properties = []
    for hedge_property in ALL_HEDGE_PROPERTIES:
        if row.get(hedge_property, False):
            hedge_properties.append(hedge_property)

    return SpeciesMap(
        species=species,
        map=smf.map,
        species_map_file=smf,
        hedge_types=hedge_types,
        hedge_properties=hedge_properties,
    )
