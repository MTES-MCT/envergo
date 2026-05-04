from django.core.management.base import BaseCommand, CommandError

from envergo.geodata.models import Map
from envergo.moulinette.models import Criterion, Regulation


class Command(BaseCommand):
    help = "Crée le critère ICPE cas par cas (staff-only) pour l'évaluation environnementale"

    def handle(self, *args, **options):
        try:
            activation_map = Map.objects.get(name="France")
        except Map.DoesNotExist:
            raise CommandError("Carte 'France' introuvable en base.")

        try:
            regulation = Regulation.objects.get(regulation="eval_env")
        except Regulation.DoesNotExist:
            raise CommandError("Regulation 'eval_env' introuvable en base.")

        criterion, created = Criterion.objects.get_or_create(
            evaluator="envergo.moulinette.regulations.evalenv.ICPE",
            activation_map=activation_map,
            regulation=regulation,
            defaults={
                "backend_title": "ICPE cas par cas (staff-only)",
                "title": "Installation classée (ICPE)",
                "subtitle": "Examen au cas par cas",
                "is_optional": True,
                "is_staff_only": True,
                "weight": 100,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Critère ICPE créé (id={criterion.pk})")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Critère ICPE existait déjà (id={criterion.pk})")
            )
