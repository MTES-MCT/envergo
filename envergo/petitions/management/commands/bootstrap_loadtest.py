"""Create the deterministic dataset used by the load tests in perf/.

Idempotent: safe to re-run after each database import. Produces
perf/fixtures.json, consumed by perf/locustfile.py and
perf/profile_endpoints.py.

Refuses to run outside a load-test environment: this command writes
synthetic accounts and dossiers, which must never reach production.
"""

import json
import secrets
import uuid
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from envergo.geodata.models import Department
from envergo.hedges.models import HedgeData
from envergo.moulinette.models import ConfigHaie
from envergo.petitions.models import PetitionProject, Simulation, StatusLog
from envergo.users.models import User

ALLOWED_ENV_NAMES = {"local", "loadtest"}
SAFE_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}

INSTRUCTOR_EMAIL = "loadtest-instructor@example.com"
PROJECT_REFERENCE = "LOADTEST"

FIXTURES_PATH = settings.ROOT_DIR / "perf" / "fixtures.json"
DEFAULT_HEDGES_PATH = settings.ROOT_DIR / "perf" / "hedge_body.json"


class Command(BaseCommand):
    help = "Create the load-test dataset (instructor, dossier, fixtures.json)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--department",
            default="14",
            help="Department code the dossier belongs to (default: 14)",
        )
        parser.add_argument(
            "--hedges-file",
            default=str(DEFAULT_HEDGES_PATH),
            help="JSON file with the hedge drawings (must lie in the department)",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Instructor password (default: generated)",
        )

    def handle(self, *args, **options):
        self.check_environment()

        department = self.get_department(options["department"])
        hedge_data = self.create_hedge_data(options["hedges_file"])
        sim_params = self.build_sim_params(department, hedge_data)
        project = self.create_project(department, hedge_data, sim_params)
        password = self.create_instructor(department, options["password"])
        self.self_check(project)

        fixtures = {
            "department": department.department,
            "project_reference": project.reference,
            "hedge_uuid": str(hedge_data.id),
            "sim_params": sim_params,
            "instructor_email": INSTRUCTOR_EMAIL,
            "instructor_password": password,
        }
        FIXTURES_PATH.parent.mkdir(exist_ok=True)
        FIXTURES_PATH.write_text(json.dumps(fixtures, indent=2))
        self.stdout.write(self.style.SUCCESS(f"Fixtures written to {FIXTURES_PATH}"))

    def check_environment(self):
        """Refuse to run anywhere but a load-test environment.

        Guards are redundant on purpose: any single one blocks
        production (ENV_NAME=production, DS enabled, anymail backend).
        """
        if settings.ENV_NAME not in ALLOWED_ENV_NAMES:
            raise CommandError(
                f"ENV_NAME is '{settings.ENV_NAME}', expected one of "
                f"{sorted(ALLOWED_ENV_NAMES)}. This command only runs in "
                "load-test environments."
            )
        if settings.DEMARCHE_NUMERIQUE["ENABLED"]:
            raise CommandError(
                "The DS API is enabled: this is not a load-test environment."
            )
        if settings.EMAIL_BACKEND not in SAFE_EMAIL_BACKENDS:
            raise CommandError(
                f"EMAIL_BACKEND '{settings.EMAIL_BACKEND}' can send real "
                "emails: this is not a load-test environment."
            )

    def get_department(self, code):
        try:
            department = Department.objects.defer("geometry").get(department=code)
        except Department.DoesNotExist:
            raise CommandError(f"Department {code} not found")

        config = ConfigHaie.objects.filter(
            department=department, is_activated=True
        ).valid_at(date.today())
        if not config.exists():
            raise CommandError(
                f"Department {code} has no activated ConfigHaie valid today"
            )
        return department

    def create_hedge_data(self, hedges_file):
        try:
            with open(hedges_file) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise CommandError(f"Cannot read hedges file {hedges_file}: {e}")

        # Stable UUID so fixtures survive re-imports without churn
        hedge_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "envergo/loadtest/hedges")
        hedge_data, created = HedgeData.objects.get_or_create(
            id=hedge_uuid, defaults={"data": data}
        )
        if not created:
            hedge_data.data = data
            hedge_data.save()
        label = "created" if created else "updated"
        self.stdout.write(f"HedgeData {hedge_uuid} {label}")
        return hedge_data

    def build_sim_params(self, department, hedge_data):
        return urlencode(
            {
                "department": department.department,
                "element": "haie",
                "travaux": "destruction",
                "contexte": "non",
                "motif": "amelioration_culture",
                "reimplantation": "replantation",
                "localisation_pac": "non",
                "date": date.today().isoformat(),
                "haies": str(hedge_data.id),
            }
        )

    def create_project(self, department, hedge_data, sim_params):
        moulinette_url = (
            f"https://{settings.ENVERGO_HAIE_DOMAIN}"
            f"/simulateur/resultat-plantation/?{sim_params}"
        )
        project, created = PetitionProject.objects.get_or_create(
            reference=PROJECT_REFERENCE,
            defaults={
                "moulinette_url": moulinette_url,
                "department": department,
                "hedge_data": hedge_data,
                "_category": "hru",
                "demarche_numerique_state": "en_construction",
                "demarche_numerique_dossier_number": 99999999,
            },
        )
        if not created:
            project.moulinette_url = moulinette_url
            project.department = department
            project.hedge_data = hedge_data
            project.save()

        if not project.status_history.exists():
            StatusLog.objects.create(
                petition_project=project,
                update_comment="Création initiale (load test)",
            )
        simulation, sim_created = Simulation.objects.get_or_create(
            project=project,
            is_initial=True,
            defaults={
                "is_active": True,
                "moulinette_url": moulinette_url,
                "comment": "Simulation initiale (load test)",
            },
        )
        # The initial simulation mirrors the project URL, which changes
        # across runs (its date param tracks the bootstrap day).
        if not sim_created and simulation.moulinette_url != moulinette_url:
            simulation.moulinette_url = moulinette_url
            simulation.save()
        label = "created" if created else "updated"
        self.stdout.write(f"PetitionProject {PROJECT_REFERENCE} {label}")
        return project

    def create_instructor(self, department, password):
        password = password or secrets.token_urlsafe(16)
        user, created = User.objects.get_or_create(
            email=INSTRUCTOR_EMAIL, defaults={"name": "Load Test Instructor"}
        )
        user.is_active = True
        user.access_haie = True
        user.is_instructor = True
        user.set_password(password)
        user.save()
        user.departments.add(department)
        label = "created" if created else "updated"
        self.stdout.write(f"Instructor {INSTRUCTOR_EMAIL} {label}")
        return password

    def self_check(self, project):
        """Fail loudly if the dossier does not actually render."""
        client = Client(HTTP_HOST=settings.ENVERGO_HAIE_DOMAIN)
        url = f"/projet/{project.reference}/consultation/"
        response = client.get(url)
        if response.status_code != 200:
            raise CommandError(
                f"Self-check failed: GET {url} returned {response.status_code}. "
                "The generated dossier does not evaluate correctly."
            )
        self.stdout.write("Self-check OK: consultation page renders")
