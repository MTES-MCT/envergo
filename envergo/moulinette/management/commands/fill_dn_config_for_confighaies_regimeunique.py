"""
Commande one-shot pour assigner la démarche numérique "régime unique" aux ConfigHaie qui en ont besoin.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from envergo.demarchenumerique.models import DemarcheConfig
from envergo.moulinette.models import ConfigHaie


class Command(BaseCommand):
    help = "Assigne la démarche numérique passée en paramètre aux ConfigHaie qui n'ont pas de démarche associée"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Vérifie les prérequis sans modifier la base de données",
        )
        parser.add_argument("demarche_number", help="Numéro de la démarche numérique")

    @transaction.atomic
    def handle(self, demarche_number, *args, **options):
        self.dry_run = options["dry_run"]

        try:
            dn_config = DemarcheConfig.objects.get(
                demarche_numerique_number=demarche_number
            )
        except DemarcheConfig.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"La démarche {demarche_number} n’est pas configurée dans l’admin."
                )
            )
            numbers = DemarcheConfig.objects.order_by(
                "demarche_numerique_number"
            ).values_list("demarche_numerique_number", flat=True)
            self.stdout.write(
                self.style.ERROR(
                    f"Démarches disponibles : {', '.join(str(n) for n in numbers)}"
                )
            )
            return

        configs_haie = ConfigHaie.objects.filter(demarche_numerique_config__isnull=True)
        if not configs_haie.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Aucune config haie non associée à un objet DN. => Arrêt"
                )
            )
            return

        self.stdout.write(f"{configs_haie.count()} configs à mettre à jour.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Association en cours avec la démarche « {dn_config.display_name} » !"
            )
        )

        for conf in configs_haie.order_by("department__department"):
            self.stdout.write(f"MAJ de {conf}")
            conf.demarche_numerique_config = dn_config
            conf.save()

        if self.dry_run:
            transaction.set_rollback(True)
            self.stdout.write(
                self.style.SUCCESS(
                    "\n=== Dry run terminé, toutes les modifications ont été annulées ==="
                )
            )
