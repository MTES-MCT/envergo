"""Measure SQL query counts and response times for Haie endpoints.

Runs each endpoint twice (cold/warm) through the Django test client
against the local dev database. Dumps full query logs as JSON for
detailed analysis.

Usage:
    USE_DEBUG_TOOLBAR=no DJANGO_SETTINGS_MODULE=config.settings.local \
        .venv/bin/python profile_endpoints.py
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import django

django.setup()

from django.db import connection, reset_queries
from django.test import Client
from django.test.utils import CaptureQueriesContext

OUT_DIR = Path(__file__).resolve().parent / "results"

HOST = "haie.local"

try:
    FIXTURES = json.loads(
        (Path(__file__).resolve().parent / "fixtures.json").read_text()
    )
except FileNotFoundError:
    raise SystemExit(
        "perf/fixtures.json not found. Run `manage.py bootstrap_loadtest` first."
    )

SIM_PARAMS = FIXTURES["sim_params"]
HEDGE_UUID = FIXTURES["hedge_uuid"]
PROJECT_REF = FIXTURES["project_reference"]
DEPARTMENT = FIXTURES["department"]
INSTRUCTOR_EMAIL = FIXTURES["instructor_email"]


def load_hedge_body():
    """Return the raw hedge data of our test HedgeData as a JSON string."""
    from envergo.hedges.models import HedgeData

    hd = HedgeData.objects.get(pk=HEDGE_UUID)
    return json.dumps(hd.data)


def build_scenarios():
    hedge_body = load_hedge_body()
    return [
        # (name, method, path, kwargs)
        ("home", "GET", "/", {}),
        ("triage", "GET", f"/simulateur/triage/?department={DEPARTMENT}&element=haie&travaux=destruction", {}),
        ("formulaire", "GET", f"/simulateur/formulaire/?{SIM_PARAMS}", {}),
        ("hedge_input_removal", "GET", f"/haies/{DEPARTMENT}/removal/", {}),
        (
            "hedge_input_plantation",
            "GET",
            f"/haies/{DEPARTMENT}/plantation/{HEDGE_UUID}/?{SIM_PARAMS}",
            {},
        ),
        ("resultat_d", "GET", f"/simulateur/resultat/?{SIM_PARAMS}", {}),
        ("resultat_p", "GET", f"/simulateur/resultat-plantation/?{SIM_PARAMS}", {}),
        (
            "hedge_conditions",
            "POST",
            f"/haies/conditions/?{SIM_PARAMS}",
            {"data": hedge_body, "content_type": "application/json"},
        ),
        ("consultation", "GET", f"/projet/{PROJECT_REF}/consultation/", {}),
        # Instructor views (auth)
        ("liste_dossiers", "GET", "/projet/liste", {"auth": True}),
        ("instruction_synthese", "GET", f"/projet/{PROJECT_REF}/instruction/", {"auth": True}),
        (
            "instruction_regulation_ep",
            "GET",
            f"/projet/{PROJECT_REF}/instruction/ep/",
            {"auth": True},
        ),
        (
            "instruction_procedure",
            "GET",
            f"/projet/{PROJECT_REF}/instruction/procedure/",
            {"auth": True},
        ),
        (
            "instruction_alternatives",
            "GET",
            f"/projet/{PROJECT_REF}/instruction/alternatives/",
            {"auth": True},
        ),
        (
            "instruction_notes",
            "GET",
            f"/projet/{PROJECT_REF}/instruction/notes/",
            {"auth": True},
        ),
        ("export_gpkg", "GET", f"/projet/{PROJECT_REF}/haies.gpkg", {}),
    ]


def run_one(client, method, path, kwargs):
    """Run a single request, return (status, seconds, queries)."""
    call_kwargs = {"HTTP_HOST": HOST}
    if "data" in kwargs:
        call_kwargs["data"] = kwargs["data"]
    if "content_type" in kwargs:
        call_kwargs["content_type"] = kwargs["content_type"]

    reset_queries()
    with CaptureQueriesContext(connection) as ctx:
        start = time.monotonic()
        try:
            if method == "GET":
                response = client.get(path, **call_kwargs)
            else:
                response = client.post(path, **call_kwargs)
            status = response.status_code
        except Exception as e:
            status = f"EXC:{type(e).__name__}"
        elapsed = time.monotonic() - start
    queries = [{"sql": q["sql"], "time": q["time"]} for q in ctx.captured_queries]
    return status, elapsed, queries


def main():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    instructor = User.objects.get(email=INSTRUCTOR_EMAIL)

    results = []
    query_dump = {}

    for name, method, path, kwargs in build_scenarios():
        client = Client()
        if kwargs.get("auth"):
            client.force_login(instructor)

        runs = []
        for run_label in ("cold", "warm"):
            status, elapsed, queries = run_one(client, method, path, kwargs)
            runs.append(
                {
                    "run": run_label,
                    "status": status,
                    "time_s": round(elapsed, 3),
                    "num_queries": len(queries),
                    "sql_time_s": round(sum(float(q["time"]) for q in queries), 3),
                }
            )
            query_dump[f"{name}_{run_label}"] = queries

        results.append({"name": name, "method": method, "path": path, "runs": runs})

        r0, r1 = runs
        print(
            f"{name:28} {method:4} "
            f"cold: {r0['status']} {r0['num_queries']:3}q {r0['time_s']:6.2f}s | "
            f"warm: {r1['status']} {r1['num_queries']:3}q {r1['time_s']:6.2f}s",
            flush=True,
        )

    OUT_DIR.mkdir(exist_ok=True)
    with open(f"{OUT_DIR}/profile_results.json", "w") as f:
        json.dump(results, f, indent=2)
    with open(f"{OUT_DIR}/profile_queries.json", "w") as f:
        json.dump(query_dump, f, indent=2)
    print(f"\nDumped results to {OUT_DIR}/profile_results.json")
    print(f"Dumped full SQL to {OUT_DIR}/profile_queries.json")


if __name__ == "__main__":
    main()
