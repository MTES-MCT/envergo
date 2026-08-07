"""Load test scenarios for the Haie site.

Two user profiles matching the audit's use cases:
- Petitioner (weight 4): UC1 simulation journey with real-time
  plantation feedback calls.
- Instructor (weight 1): UC4 list + UC5 instruction browsing.

Excluded on purpose: POST /projet/ (DS API), messagerie/dossier-complet
(DS API), register/newsletter (side-effect endpoints).

Usage:
    locust -f locustfile.py --host http://127.0.0.1:8001 \
        --headless -u <users> -r <spawn rate> -t <duration>
"""

import json
from pathlib import Path

from locust import HttpUser, between, task

HERE = Path(__file__).parent
HEDGE_BODY = (HERE / "hedge_body.json").read_text().strip()

try:
    FIXTURES = json.loads((HERE / "fixtures.json").read_text())
except FileNotFoundError:
    raise SystemExit(
        "perf/fixtures.json not found. Run `manage.py bootstrap_loadtest` first."
    )

HOST_HEADER = {"Host": "haie.local"}

SIM_PARAMS = FIXTURES["sim_params"]
HEDGE_UUID = FIXTURES["hedge_uuid"]
PROJECT_REF = FIXTURES["project_reference"]
DEPARTMENT = FIXTURES["department"]

INSTRUCTOR_EMAIL = FIXTURES["instructor_email"]
INSTRUCTOR_PASSWORD = FIXTURES["instructor_password"]


class PetitionerUser(HttpUser):
    """UC1: full simulation journey, weighted as the dominant profile."""

    weight = 4
    wait_time = between(2, 8)

    def on_start(self):
        self.client.headers.update(HOST_HEADER)

    @task
    def simulation_journey(self):
        self.client.get("/", name="home")
        self.client.get(
            f"/simulateur/triage/?department={DEPARTMENT}"
            "&element=haie&travaux=destruction",
            name="triage",
        )
        self.client.get(f"/simulateur/formulaire/?{SIM_PARAMS}", name="formulaire")
        self.client.get(f"/haies/{DEPARTMENT}/removal/", name="hedge_input_removal")
        self.client.get(f"/simulateur/resultat/?{SIM_PARAMS}", name="resultat_d")
        response = self.client.get(
            f"/haies/{DEPARTMENT}/plantation/{HEDGE_UUID}/?{SIM_PARAMS}",
            name="hedge_input_plantation",
        )
        # Real-time feedback loop: one conditions call per drawing change.
        csrf = response.cookies.get("csrftoken") or self.client.cookies.get(
            "csrftoken"
        )
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRFToken"] = csrf
        for _ in range(4):
            self.client.post(
                f"/haies/conditions/?{SIM_PARAMS}",
                data=HEDGE_BODY,
                headers=headers,
                name="conditions",
            )
        self.client.get(
            f"/simulateur/resultat-plantation/?{SIM_PARAMS}", name="resultat_p"
        )


class InstructorUser(HttpUser):
    """UC4 + UC5: dossier list and instruction browsing."""

    weight = 1
    wait_time = between(3, 10)

    def on_start(self):
        self.client.headers.update(HOST_HEADER)
        response = self.client.get("/comptes/connexion/", name="login_page")
        csrf = response.cookies.get("csrftoken") or self.client.cookies.get(
            "csrftoken"
        )
        self.client.post(
            "/comptes/connexion/",
            data={
                "username": INSTRUCTOR_EMAIL,
                "password": INSTRUCTOR_PASSWORD,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": "http://haie.local/comptes/connexion/"},
            name="login",
        )

    @task(3)
    def browse_list(self):
        self.client.get("/projet/liste", name="liste_dossiers")

    @task(2)
    def review_dossier(self):
        self.client.get(
            f"/projet/{PROJECT_REF}/instruction/", name="instruction_synthese"
        )
        self.client.get(
            f"/projet/{PROJECT_REF}/instruction/ep/", name="instruction_regulation"
        )

    @task(1)
    def check_procedure(self):
        self.client.get(
            f"/projet/{PROJECT_REF}/instruction/procedure/",
            name="instruction_procedure",
        )
