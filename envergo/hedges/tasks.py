import csv
import logging

from django.db import transaction
from django.utils import timezone

from config.celery_app import app
from envergo.hedges.models import (
    HEDGE_TYPES,
    IMPORT_STATUSES,
    Species,
    SpeciesMap,
    SpeciesMapFile,
)

logger = logging.getLogger(__name__)


@app.task(bind=True)
@transaction.atomic
def process_species_map_file(task, object_id):
    smf = SpeciesMapFile.objects.get(pk=object_id)
    all_hedge_types = dict(HEDGE_TYPES).keys()
    import_log = []

    # Store the task data in the model, so we can display progression
    # in the admin page.
    smf.task_id = task.request.id
    smf.import_log = ""
    smf.import_status = None
    smf.save()

    # Clear existing data
    SpeciesMap.objects.filter(species_map_file=smf).delete()

    # Process csv file
    species_map_files = []
    with open(smf.file.path, "r") as csvfile:
        nb_lines = 0
        reader = csv.DictReader(csvfile)
        for row in reader:
            nb_lines += 1

            try:
                species = Species.objects.get(taxref_ids__contains=[row["CD_NOM"]])
            except Species.DoesNotExist:
                msg = f"Espèce inconnue {row["Nom commun"]}"
                import_log.append(msg)
                continue

            hedge_types = []
            for hedge_type in all_hedge_types:
                if bool(row[hedge_type]):
                    hedge_types.append(hedge_type)

            species_map_files.append(
                SpeciesMap(
                    species=species,
                    map=smf.map,
                    species_map_file=smf,
                    hedge_types=hedge_types,
                    proximite_mare=bool(row["proximite_mare"]),
                    proximite_point_eau=bool(row["proximite_point_eau"]),
                    connexion_boisement=bool(row["connexion_boisement"]),
                    vieil_arbre=bool(row["vieil_arbre"]),
                )
            )

    # Create objects with a single query
    objects = SpeciesMap.objects.bulk_create(species_map_files)

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
