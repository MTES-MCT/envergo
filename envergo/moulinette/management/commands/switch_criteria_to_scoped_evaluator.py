from django.core.management.base import BaseCommand

from envergo.geodata.models import Map
from envergo.moulinette.models import Criterion, Regulation

SWITCHES = [
    (
        "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaie",
        "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieHru",
        "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieRu",
        "envergo.moulinette.regulations.urbanisme_haie.UrbanismeHaieL3503",
    ),
    (
        "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaie",
        "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieHru",
        "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieRu",
        "envergo.moulinette.regulations.protection_captages.ProtectionCaptagesHaieL3503",
    ),
    (
        "envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
        "envergo.moulinette.regulations.alignementarbres.AlignementsArbresHru",
        "envergo.moulinette.regulations.alignementarbres.AlignementsArbresRu",
        "envergo.moulinette.regulations.alignementarbres.AlignementsArbresL3503",
    ),
    (
        "envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaie",
        "envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieHru",
        "envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRu",
        "envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieL3503",
    ),
]


class Command(BaseCommand):
    help = (
        "To be run only once. Switch GUH criterion evaluator to scoped evaluator (RU, L350-3 and HRU). "
        "Create the Régime unique haie régulation and criteria if they are missing."
    )

    def handle(self, *args, **options):
        if not Regulation.objects.filter(regulation="regime_unique_haie").exists():
            france = Map.objects.get(name="France")
            regulation = Regulation.objects.create(
                regulation="regime_unique_haie",
                evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRegulation",
            )
            Criterion.objects.create(
                regulation=regulation,
                evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaie",
                activation_map_id=france.pk,
                backend_title="Régime unique haie",
                activation_mode="department_centroid",
            )

        for old, hru, ru, l350_3 in SWITCHES:
            backend_title = (
                Criterion.objects.filter(evaluator=old)
                .values_list("backend_title", flat=True)
                .first()
            )
            if not backend_title:
                continue
            Criterion.objects.filter(evaluator=old).update(
                evaluator=hru, backend_title=f"{backend_title} - Hors régime unique"
            )
            criterion = Criterion.objects.filter(evaluator=hru).first()
            if criterion:
                criterion.pk = None
                criterion.evaluator = ru
                criterion.backend_title = f"{backend_title} - Régime unique"
                criterion.save()

                criterion.pk = None
                criterion.evaluator = l350_3
                criterion.backend_title = f"{backend_title} - L350-3"
                criterion.save()
