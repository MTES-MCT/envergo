"""Match components against the OSV vulnerability database (https://osv.dev)."""

from dataclasses import dataclass
from itertools import chain

import requests
from cvss import CVSS3, CVSS4
from django.conf import settings
from packaging.utils import canonicalize_name

OSV_API_URL = "https://api.osv.dev/v1"
GHSA_PREFIX = "GHSA-"
MALICIOUS_PREFIX = "MAL-"
SHORT_COMMIT_LENGTH = 12  # Long enough to stay unique in large repositories.

# CVSS ratings in the dashboard's words. A zero score has the rating "None".
CVSS_RATINGS = {
    "Critical": "critical",
    "High": "high",
    "Medium": "moderate",
    "Low": "low",
    "None": "low",
}


@dataclass(frozen=True)
class Finding:
    """One known flaw affecting a component."""

    id: str
    summary: str
    severity: str  # An OSV rating in lowercase, "malicious" or "unknown".
    fixed_versions: list[str]


class OsvRecord:
    """One OSV vulnerability record. The only code that knows OSV's JSON layout."""

    def __init__(self, data):
        self.data = data

    @property
    def id(self):
        """Return the record's own identifier, such as "GHSA-…" or "CVE-…"."""
        return self.data["id"]

    @property
    def summary(self):
        """Return the record's one-line summary, or an empty string."""
        return self.data.get("summary", "")

    @property
    def identifiers(self):
        """Return every name of the flaw: the record's own id and its aliases."""
        return {self.id, *self.data.get("aliases", [])}

    @property
    def is_ghsa(self):
        """Tell whether GitHub published the record. Such records carry a rating."""
        return self.id.startswith(GHSA_PREFIX)

    @property
    def is_malicious(self):
        """Tell whether the record reports a malicious release."""
        return any(name.startswith(MALICIOUS_PREFIX) for name in self.identifiers)

    @property
    def github_rating(self):
        """Return GitHub's rating word, such as "HIGH", or None."""
        return self.data.get("database_specific", {}).get("severity")

    @property
    def cvss_vectors(self):
        """Return the CVSS vectors by CVSS version, such as {"CVSS_V3": "CVSS:3.1/…"}."""
        # OSV names this list "severity". It holds vectors, not ratings.
        return {
            score["type"]: score["score"] for score in self.data.get("severity", [])
        }

    def fixed_versions(self, component):
        """Return the versions, or short commits, that fix this flaw for `component`."""
        all_entries = self.data.get("affected", [])
        our_entries = [entry for entry in all_entries if describes(entry, component)]
        ranges = chain.from_iterable(entry.get("ranges", []) for entry in our_entries)
        fixes = chain.from_iterable(read_range_fixes(r) for r in ranges)
        return list(fixes)


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
    data = call_osv("GET", f"vulns/{record_id}")
    return OsvRecord(data)


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
    ghsa_records = [record for record in records if record.is_ghsa]
    other_records = [record for record in records if not record.is_ghsa]

    kept_records = []
    seen_identifiers = set()
    for record in ghsa_records + other_records:
        if record.identifiers & seen_identifiers:
            continue
        seen_identifiers |= record.identifiers
        kept_records.append(record)
    return kept_records


def to_finding(component, record):
    """Build a finding from the parts of an OSV record the dashboard shows."""
    return Finding(
        id=record.id,
        summary=record.summary,
        severity=rate(record),
        fixed_versions=record.fixed_versions(component),
    )


def rate(record):
    """Return the dashboard's severity word for a record."""
    if record.is_malicious:
        return "malicious"

    if record.github_rating:
        severity = record.github_rating.lower()
    else:
        severity = rate_cvss(record.cvss_vectors) or "unknown"
    return severity


def rate_cvss(cvss_vectors):
    """Turn the newest CVSS vector into a dashboard word, or return None."""
    rating = None
    if "CVSS_V4" in cvss_vectors:
        rating = CVSS4(cvss_vectors["CVSS_V4"]).severity
    elif "CVSS_V3" in cvss_vectors:
        base_rating, _, _ = CVSS3(cvss_vectors["CVSS_V3"]).severities()
        rating = base_rating
    return CVSS_RATINGS.get(rating)


def describes(affected_entry, component):
    """Tell whether one `affected` entry of a record is about the scanned library.

    Entries for C libraries name no package, only the repository of each commit range.
    """
    if "package" in affected_entry:
        is_about_component = is_same_package(component, affected_entry["package"])
    else:
        ranges = affected_entry["ranges"]
        repositories = [version_range.get("repo") for version_range in ranges]
        is_about_component = component.name in repositories
    return is_about_component


def read_range_fixes(version_range):
    """Return the versions fixing one range. Git ranges give short commits instead."""
    events = version_range["events"]
    fixes = [event["fixed"] for event in events if "fixed" in event]
    if version_range["type"] == "GIT":
        fixes = [commit[:SHORT_COMMIT_LENGTH] for commit in fixes]
    return fixes


def is_same_package(component, osv_package):
    """Tell whether an OSV package entry is this component, whatever the name's spelling.

    PyPI's spelling rules are harmless on npm names, so they apply to both ecosystems.
    """
    same_ecosystem = component.ecosystem == osv_package["ecosystem"]

    component_name = canonicalize_name(component.name)
    osv_name = canonicalize_name(osv_package["name"])
    same_name = component_name == osv_name

    return same_ecosystem and same_name
