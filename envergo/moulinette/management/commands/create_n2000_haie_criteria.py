"""
Commande one-off pour créer les critères Natura 2000 Haie manquants.

Contexte :
- N2000 Haie est une réglementation à périmètres.
- Chaque département a un périmètre N2000 (partagé entre GUH et Envergo).
- Les critères déjà créés manuellement (02, 14, Bretagne) sont ignorés via get_or_create.
- Les évaluateurs ont 2 paramètres : result (soumis/non_soumis) et concerne_aa (oui/non).

Étapes :
1. Renomme les 66 cartes cas 2 (32 départements × 2 cartes) :
   - "N2000 Haie XX" → "N2000 Haie XX – soumis"
   - "N2000 Haie XX – NC" → "N2000 Haie XX – non soumis"
2. Crée 63 critères cas 1 (1 par département, carte unique "N2000 XX")
3. Crée 64 critères cas 2 (2 par département, cartes "N2000 Haie XX – soumis/non soumis")

Local:   docker compose run --rm django python manage.py create_n2000_haie_criteria
Staging: scalingo --app envergo-staging run python manage.py create_n2000_haie_criteria
Prod:    scalingo --app envergo run python manage.py create_n2000_haie_criteria
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from envergo.geodata.models import Map
from envergo.moulinette.models import Criterion, Perimeter, Regulation

EVALUATOR = "envergo.moulinette.regulations.natura2000_haie.Natura2000Haie"

# Départements dont les critères ont déjà été créés manuellement
ALREADY_CREATED = {"02", "14", "22", "29", "35", "56"}

# Cas 1 : départements homogènes (1 carte, 1 critère)
# Le résultat est le même sur tout le département.
# (code_département, result, concerne_aa)
CASE_1 = [
    ("01", "soumis", "non"),
    ("03", "non_soumis", "non"),
    ("04", "non_soumis", "non"),
    ("05", "non_soumis", "non"),
    ("06", "non_soumis", "non"),
    ("07", "non_soumis", "non"),
    ("09", "non_soumis", "non"),
    ("11", "non_soumis", "non"),
    ("12", "non_soumis", "non"),
    ("13", "non_soumis", "non"),
    ("16", "soumis", "non"),
    ("19", "non_soumis", "non"),
    ("23", "non_soumis", "non"),
    ("24", "non_soumis", "non"),
    ("25", "soumis", "non"),
    ("26", "soumis", "non"),
    ("27", "soumis", "non"),
    ("28", "non_soumis", "non"),
    ("30", "non_soumis", "non"),
    ("31", "non_soumis", "non"),
    ("32", "non_soumis", "non"),
    ("33", "non_soumis", "non"),
    ("34", "non_soumis", "non"),
    ("38", "soumis", "non"),
    ("39", "soumis", "oui"),
    ("40", "non_soumis", "non"),
    ("44", "soumis", "non"),
    ("45", "non_soumis", "non"),
    ("46", "non_soumis", "non"),
    ("47", "non_soumis", "non"),
    ("54", "non_soumis", "non"),
    ("57", "soumis", "non"),
    ("58", "soumis", "non"),
    ("60", "non_soumis", "non"),
    ("62", "soumis", "non"),
    ("64", "non_soumis", "non"),
    ("66", "non_soumis", "non"),
    ("67", "soumis", "non"),
    ("68", "soumis", "non"),
    ("69", "soumis", "non"),
    ("73", "non_soumis", "non"),
    ("75", "non_soumis", "non"),
    ("76", "soumis", "non"),
    ("78", "soumis", "non"),
    ("79", "soumis", "non"),
    ("80", "soumis", "non"),
    ("81", "non_soumis", "non"),
    ("82", "soumis", "oui"),
    ("83", "non_soumis", "non"),
    ("84", "non_soumis", "non"),
    ("85", "soumis", "non"),
    ("86", "soumis", "non"),
    ("87", "non_soumis", "non"),
    ("91", "non_soumis", "non"),
    ("92", "non_soumis", "non"),
    ("93", "non_soumis", "non"),
    ("94", "non_soumis", "non"),
    ("95", "soumis", "non"),
    ("971", "non_soumis", "non"),
    ("972", "non_soumis", "non"),
    ("973", "non_soumis", "non"),
    ("974", "non_soumis", "non"),
    ("976", "non_soumis", "non"),
]

# Cas 2 : départements hétérogènes (2 cartes, 2 critères)
# Certaines zones du département sont "soumis", d'autres "non_soumis",
# donc on a 2 cartes distinctes et 2 critères par département.
# (code_département, result, concerne_aa)
CASE_2 = [
    ("08", "non_soumis", "non"),
    ("08", "soumis", "non"),
    ("10", "non_soumis", "non"),
    ("10", "soumis", "non"),
    ("15", "non_soumis", "non"),
    ("15", "soumis", "non"),
    ("17", "non_soumis", "non"),
    ("17", "soumis", "non"),
    ("18", "non_soumis", "non"),
    ("18", "soumis", "non"),
    ("21", "non_soumis", "non"),
    ("21", "soumis", "non"),
    ("2A", "non_soumis", "non"),
    ("2A", "soumis", "non"),
    ("2B", "non_soumis", "non"),
    ("2B", "soumis", "non"),
    ("36", "non_soumis", "non"),
    ("36", "soumis", "non"),
    ("37", "non_soumis", "non"),
    ("37", "soumis", "non"),
    ("41", "non_soumis", "non"),
    ("41", "soumis", "non"),
    ("42", "non_soumis", "non"),
    ("42", "soumis", "non"),
    ("43", "non_soumis", "non"),
    ("43", "soumis", "non"),
    ("48", "non_soumis", "non"),
    ("48", "soumis", "non"),
    ("49", "non_soumis", "non"),
    ("49", "soumis", "non"),
    ("50", "non_soumis", "non"),
    ("50", "soumis", "non"),
    ("51", "non_soumis", "non"),
    ("51", "soumis", "non"),
    ("52", "non_soumis", "non"),
    ("52", "soumis", "non"),
    ("53", "non_soumis", "non"),
    ("53", "soumis", "non"),
    ("55", "non_soumis", "non"),
    ("55", "soumis", "non"),
    ("59", "non_soumis", "non"),
    ("59", "soumis", "non"),
    ("61", "non_soumis", "non"),
    ("61", "soumis", "non"),
    ("63", "non_soumis", "non"),
    ("63", "soumis", "non"),
    ("65", "non_soumis", "oui"),
    ("65", "soumis", "oui"),
    ("70", "non_soumis", "non"),
    ("70", "soumis", "non"),
    ("71", "non_soumis", "non"),
    ("71", "soumis", "non"),
    ("72", "non_soumis", "non"),
    ("72", "soumis", "non"),
    ("74", "non_soumis", "non"),
    ("74", "soumis", "non"),
    ("77", "non_soumis", "non"),
    ("77", "soumis", "non"),
    ("88", "non_soumis", "non"),
    ("88", "soumis", "non"),
    ("89", "non_soumis", "non"),
    ("89", "soumis", "non"),
    ("90", "non_soumis", "non"),
    ("90", "soumis", "non"),
]

CASE_1_DEPARTMENTS = {dept for dept, _, _ in CASE_1}
CASE_2_DEPARTMENTS = {dept for dept, _, _ in CASE_2}
ALL_DEPARTMENTS = sorted(ALREADY_CREATED | CASE_1_DEPARTMENTS | CASE_2_DEPARTMENTS)


class Command(BaseCommand):
    help = "Crée les critères Natura 2000 Haie pour tous les départements"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Vérifie les prérequis sans modifier la base de données",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]

        # Étape 0 : vérifier que toutes les données requises sont en base
        self.stdout.write("=== Vérification des prérequis ===")
        self.check_prerequisites()

        regulation = Regulation.objects.get(regulation="natura2000_haie")

        # Étape 1 : vérifier que les critères déjà créés existent bien
        self.stdout.write("\n=== Vérification des critères existants ===")
        self.check_existing_criteria(regulation)

        # Étape 2 : renommer les cartes des départements cas 2
        # avant de créer les critères qui les référencent
        self.stdout.write("\n=== Renommage des cartes cas 2 ===")
        self.rename_case2_maps()

        # Étape 3 : créer les critères cas 1 (1 critère par département)
        self.stdout.write("\n=== Création des critères cas 1 ===")
        self.create_case1_criteria(regulation)

        # Étape 4 : créer les critères cas 2 (2 critères par département)
        self.stdout.write("\n=== Création des critères cas 2 ===")
        self.create_case2_criteria(regulation)

        if self.dry_run:
            transaction.set_rollback(True)
            self.stdout.write(
                self.style.SUCCESS(
                    "\n=== Dry run terminé, toutes les modifications ont été annulées ==="
                )
            )

    def check_prerequisites(self):
        errors = []

        # Réglementation
        if not Regulation.objects.filter(regulation="natura2000_haie").exists():
            errors.append("Réglementation 'natura2000_haie' introuvable")

        # Périmètres : N2000 XX pour chaque département
        existing_perimeters = set(
            Perimeter.objects.filter(
                backend_name__in=[f"N2000 {d}" for d in ALL_DEPARTMENTS]
            ).values_list("backend_name", flat=True)
        )
        for dept in ALL_DEPARTMENTS:
            if f"N2000 {dept}" not in existing_perimeters:
                errors.append(f"Périmètre 'N2000 {dept}' introuvable")

        # Cartes cas 1 : N2000 XX
        case1_map_names = [f"N2000 {dept}" for dept, _, _ in CASE_1]
        existing_maps = set(
            Map.objects.filter(name__in=case1_map_names).values_list("name", flat=True)
        )
        for dept, _, _ in CASE_1:
            map_name = f"N2000 {dept}"
            if map_name not in existing_maps:
                errors.append(f"Carte cas 1 '{map_name}' introuvable")

        # Cartes cas 2 : anciens noms (avant renommage)
        for dept in CASE_2_DEPARTMENTS:
            for map_name in [f"N2000 Haie {dept}", f"N2000 Haie {dept} – NC"]:
                if not Map.objects.filter(name=map_name).exists():
                    errors.append(f"Carte cas 2 '{map_name}' introuvable")

        if errors:
            self.stderr.write(self.style.ERROR("Prérequis manquants :"))
            for error in errors:
                self.stderr.write(self.style.ERROR(f"  - {error}"))
            raise CommandError(f"{len(errors)} prérequis manquant(s), abandon.")
        else:
            self.stdout.write(self.style.SUCCESS("  Tous les prérequis sont validés"))

    def check_existing_criteria(self, regulation):
        """Vérifie que les départements déjà créés (02, 14, 22, 29, 35, 56)
        ont bien au moins un critère N2000 Haie en base."""
        for dept in sorted(ALREADY_CREATED):
            exists = Criterion.objects.filter(
                evaluator=EVALUATOR,
                regulation=regulation,
                backend_title__startswith=f"N2000 Haie > {dept}",
            ).exists()
            if exists:
                self.stdout.write(self.style.SUCCESS(f"  {dept} : critère existant OK"))
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"  {dept} : AUCUN critère trouvé alors qu'il"
                        f" devrait déjà exister"
                    )
                )

    def rename_case2_maps(self):
        """Renomme les cartes des départements cas 2.

        Avant : "N2000 Haie XX" (zones soumises) et "N2000 Haie XX – NC" (zones non concernées)
        Après : "N2000 Haie XX – soumis" et "N2000 Haie XX – non soumis"

        Utilise filter().update() pour ne rien faire si la carte n'existe pas
        ou a déjà été renommée (idempotent).
        """
        for dept in CASE_2_DEPARTMENTS:
            old_soumis = f"N2000 Haie {dept}"
            new_soumis = f"N2000 Haie {dept} – soumis"
            old_nc = f"N2000 Haie {dept} – NC"
            new_nc = f"N2000 Haie {dept} – non soumis"

            updated = Map.objects.filter(name=old_soumis).update(name=new_soumis)
            if updated:
                self.stdout.write(f"  Renamed '{old_soumis}' → '{new_soumis}'")

            updated = Map.objects.filter(name=old_nc).update(name=new_nc)
            if updated:
                self.stdout.write(f"  Renamed '{old_nc}' → '{new_nc}'")

    def get_perimeter(self, dept):
        """Récupère le périmètre N2000 du département.

        Chaque département a un périmètre nommé "N2000 XX" qui regroupe
        tous les sites Natura 2000 du département.
        """
        perimeter_name = f"N2000 {dept}"
        try:
            return Perimeter.objects.get(backend_name=perimeter_name)
        except Perimeter.DoesNotExist:
            raise Perimeter.DoesNotExist(f"Périmètre '{perimeter_name}' introuvable")

    def get_case1_activation_map(self, dept):
        map_name = f"N2000 {dept}"
        try:
            return Map.objects.get(name=map_name)
        except Map.DoesNotExist:
            raise Map.DoesNotExist(f"Carte '{map_name}' introuvable")

    def get_case2_activation_map(self, dept, suffix):
        map_name = f"N2000 Haie {dept} – {suffix}"
        try:
            return Map.objects.get(name=map_name)
        except Map.DoesNotExist:
            raise Map.DoesNotExist(f"Carte '{map_name}' introuvable")

    def create_case1_criteria(self, regulation):
        """Crée 1 critère par département cas 1.

        Cas 1 = résultat homogène sur tout le département.
        """
        for dept, result, concerne_aa in CASE_1:
            activation_map = self.get_case1_activation_map(dept)
            perimeter = self.get_perimeter(dept)

            criterion, created = Criterion.objects.get_or_create(
                evaluator=EVALUATOR,
                activation_map=activation_map,
                regulation=regulation,
                defaults={
                    "backend_title": f"N2000 Haie > {dept}",
                    "title": "Natura 2000",
                    "perimeter": perimeter,
                    "activation_distance": 0,
                    "evaluator_settings": {
                        "result": result,
                        "concerne_aa": concerne_aa,
                    },
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created criterion {dept} (id={criterion.pk})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Criterion {dept} already exists (id={criterion.pk})"
                    )
                )

    def create_case2_criteria(self, regulation):
        """Crée 2 critères par département cas 2.

        Cas 2 = zones soumises et non soumises distinctes dans le département.
        """
        for dept, result, concerne_aa in CASE_2:
            # "soumis" dans evaluator_settings mais "non soumis" (sans underscore)
            # dans les noms de cartes et backend_title
            suffix = "soumis" if result == "soumis" else "non soumis"
            activation_map = self.get_case2_activation_map(dept, suffix)
            perimeter = self.get_perimeter(dept)

            criterion, created = Criterion.objects.get_or_create(
                evaluator=EVALUATOR,
                activation_map=activation_map,
                regulation=regulation,
                defaults={
                    "backend_title": f"N2000 Haie > {dept} – {suffix}",
                    "title": "Natura 2000",
                    "perimeter": perimeter,
                    "activation_distance": 0,
                    "evaluator_settings": {
                        "result": result,
                        "concerne_aa": concerne_aa,
                    },
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created criterion {dept} – {suffix}" f" (id={criterion.pk})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Criterion {dept} – {suffix}"
                        f" already exists (id={criterion.pk})"
                    )
                )
