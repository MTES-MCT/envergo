from envergo.security import osv
from envergo.security.inventory import Component, Ecosystem
from envergo.security.models import Severity

COMPONENT = Component("some-package", "1.0.0", Ecosystem.PYPI)


def mock_osv(monkeypatch, records):
    """Make OSV report these records as affecting `COMPONENT`."""
    records_by_id = {record["id"]: record for record in records}
    record_ids_by_component = {COMPONENT: list(records_by_id)}
    monkeypatch.setattr(osv, "query_record_ids", lambda _: record_ids_by_component)
    monkeypatch.setattr(
        osv, "fetch_record", lambda record_id: osv.OsvRecord(records_by_id[record_id])
    )


def test_aliased_records_give_one_vulnerability(monkeypatch):
    """A flaw published under two identifiers is kept once, as the rated GHSA record."""
    pysec_record = {"id": "PYSEC-1", "aliases": ["GHSA-1"]}
    ghsa_record = {
        "id": "GHSA-1",
        "aliases": ["PYSEC-1"],
        "database_specific": {"severity": "HIGH"},
    }
    mock_osv(monkeypatch, [pysec_record, ghsa_record])

    findings = osv.find_vulnerabilities([COMPONENT])[COMPONENT]

    assert [finding.id for finding in findings] == ["GHSA-1"]
    assert findings[0].severity == Severity.HIGH


def test_fixed_versions_come_from_our_package_only(monkeypatch):
    """A record covering several packages only gives the fixes of the scanned one, however its name is spelled."""
    our_ranges = [
        {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "1.0.1"}]}
    ]
    other_ranges = [
        {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "9.9.9"}]}
    ]
    record = {
        "id": "GHSA-1",
        "affected": [
            {
                "package": {"name": "Some_Package", "ecosystem": "PyPI"},
                "ranges": our_ranges,
            },
            {
                "package": {"name": "other-package", "ecosystem": "PyPI"},
                "ranges": other_ranges,
            },
        ],
    }
    mock_osv(monkeypatch, [record])

    findings = osv.find_vulnerabilities([COMPONENT])[COMPONENT]

    assert findings[0].fixed_versions == ["1.0.1"]


def test_git_record_gives_commit_fix_and_cvss_rating(monkeypatch):
    """A C library record matches by repository. It is rated from its CVSS vector."""
    repository = "https://github.com/freetype/freetype"
    git_component = Component(repository, "VER-2-14-3", Ecosystem.GIT)
    record = {
        "id": "CVE-2026-50811",
        "severity": [
            {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L"}
        ],
        "affected": [
            {
                "ranges": [
                    {
                        "type": "GIT",
                        "repo": repository,
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "f" * 40},
                        ],
                    }
                ]
            }
        ],
    }
    monkeypatch.setattr(
        osv, "query_record_ids", lambda _: {git_component: [record["id"]]}
    )
    monkeypatch.setattr(osv, "fetch_record", lambda _: osv.OsvRecord(record))

    findings = osv.find_vulnerabilities([git_component])[git_component]

    assert findings[0].fixed_versions == ["f" * 12]
    assert findings[0].severity == Severity.MODERATE
