"""Match components against the OSV vulnerability database (https://osv.dev)."""

from dataclasses import dataclass
from itertools import chain

import requests
from django.conf import settings
from packaging.utils import canonicalize_name

OSV_API_URL = "https://api.osv.dev/v1"
GHSA_PREFIX = "GHSA-"
MALICIOUS_PREFIX = "MAL-"


@dataclass(frozen=True)
class Finding:
    """One known flaw affecting a component."""

    id: str
    summary: str
    severity: str  # An OSV rating in lowercase, "malicious" or "unknown".
    fixed_versions: list[str]


def find_vulnerabilities(components):
    """Map each vulnerable component to its findings. Others are absent.

    Raises on any OSV failure: a partial result would make libraries look clean.
    """
    record_ids_by_component = query_record_ids(components)
    records_by_id = fetch_records(record_ids_by_component)

    findings_by_component = {}
    for component, record_ids in record_ids_by_component.items():
        records = [records_by_id[record_id] for record_id in record_ids]
        distinct_records = drop_aliases(records)
        findings_by_component[component] = [
            to_finding(component, record) for record in distinct_records
        ]
    return findings_by_component


def query_record_ids(components):
    """Ask OSV which record ids affect each component's exact version."""
    results = post_batch_query(components)

    record_ids_by_component = {}
    for component, result in zip(components, results, strict=True):
        # OSV paginates past 1,000 vulnerabilities per package or 3,000 per request.
        if "next_page_token" in result:
            raise RuntimeError(f"OSV paginated the results for {component}")
        record_ids = [entry["id"] for entry in result.get("vulns", [])]
        if record_ids:
            record_ids_by_component[component] = record_ids
    return record_ids_by_component


def post_batch_query(components):
    """Return OSV's result for each component, in the same order."""
    queries = [to_osv_query(component) for component in components]
    response = call_osv("POST", "querybatch", {"queries": queries})
    return response["results"]


def to_osv_query(component):
    """Build the query asking about a component's exact version."""
    package = {"name": component.name, "ecosystem": component.ecosystem}
    return {"package": package, "version": component.version}


def fetch_records(record_ids_by_component):
    """Return each full record by id, fetching each id once."""
    unique_ids = set(chain.from_iterable(record_ids_by_component.values()))
    return {record_id: fetch_record(record_id) for record_id in unique_ids}


def fetch_record(record_id):
    """Return the full OSV record of a vulnerability."""
    return call_osv("GET", f"vulns/{record_id}")


def call_osv(method, path, payload=None):
    """Send one request to OSV and return the parsed response. Raises on HTTP errors."""
    url = f"{OSV_API_URL}/{path}"
    timeout = settings.DEFAULT_HTTP_TIMEOUT
    response = requests.request(method, url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def drop_aliases(records):
    """Keep one record per flaw. OSV often lists a GHSA and a PYSEC record for it.

    GHSA records come first because they carry a severity rating.
    """
    ghsa_records = [
        record for record in records if record["id"].startswith(GHSA_PREFIX)
    ]
    other_records = [
        record for record in records if not record["id"].startswith(GHSA_PREFIX)
    ]

    kept_records = []
    seen_ids = set()
    for record in ghsa_records + other_records:
        known_ids = read_known_ids(record)
        if known_ids & seen_ids:
            continue
        seen_ids |= known_ids
        kept_records.append(record)
    return kept_records


def read_known_ids(record):
    """Return every identifier of a flaw: the record's own id and its aliases."""
    return {record["id"], *record.get("aliases", [])}


def to_finding(component, record):
    """Build a finding from the parts of an OSV record the dashboard shows."""
    return Finding(
        id=record["id"],
        summary=record.get("summary", ""),
        severity=read_severity(record),
        fixed_versions=read_fixed_versions(component, record),
    )


def read_severity(record):
    """Return the record's rating. Malicious releases have none, so they get their own."""
    known_ids = read_known_ids(record)
    if any(known_id.startswith(MALICIOUS_PREFIX) for known_id in known_ids):
        return "malicious"

    rating = record.get("database_specific", {}).get("severity")
    return rating.lower() if rating else "unknown"


def read_fixed_versions(component, record):
    """Return the versions of `component` that fix the flaw described by `record`."""
    all_entries = record.get("affected", [])
    our_entries = [
        entry for entry in all_entries if is_same_package(component, entry["package"])
    ]
    ranges = chain.from_iterable(entry.get("ranges", []) for entry in our_entries)
    events = chain.from_iterable(version_range["events"] for version_range in ranges)
    return [event["fixed"] for event in events if "fixed" in event]


def is_same_package(component, osv_package):
    """Tell whether an OSV package entry is this component, whatever the name's spelling.

    PyPI's spelling rules are harmless on npm names, so they apply to both ecosystems.
    """
    same_ecosystem = component.ecosystem == osv_package["ecosystem"]

    component_name = canonicalize_name(component.name)
    osv_name = canonicalize_name(osv_package["name"])
    same_name = component_name == osv_name

    return same_ecosystem and same_name
