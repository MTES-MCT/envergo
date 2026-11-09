from envergo.security import osv
from envergo.security.inventory import Component

COMPONENT = Component("some-package", "1.0.0", "PyPI")


def mock_osv(monkeypatch, records):
    """Make OSV report these records as affecting `COMPONENT`."""
    records_by_id = {record["id"]: record for record in records}
    record_ids_by_component = {COMPONENT: list(records_by_id)}
    monkeypatch.setattr(osv, "query_record_ids", lambda _: record_ids_by_component)
    monkeypatch.setattr(osv, "fetch_record", records_by_id.get)


def test_aliased_records_give_one_vulnerability(monkeypatch):
    """A flaw published under two identifiers is kept once, as the rated GHSA record."""
    pysec_record = {"id": "PYSEC-1", "aliases": ["GHSA-1"]}
    ghsa_record = {
        "id": "GHSA-1",
        "aliases": ["PYSEC-1"],
        "database_specific": {"severity": "HIGH"},
    }
    mock_osv(monkeypatch, [pysec_record, ghsa_record])

    vulnerabilities = osv.find_vulnerabilities([COMPONENT])[COMPONENT]

    assert [v.id for v in vulnerabilities] == ["GHSA-1"]
    assert vulnerabilities[0].severity == "high"


def test_fixed_versions_come_from_our_package_only(monkeypatch):
    """A record covering several packages only gives the fixes of the scanned one, however its name is spelled."""
    our_ranges = [{"events": [{"introduced": "0"}, {"fixed": "1.0.1"}]}]
    other_ranges = [{"events": [{"introduced": "0"}, {"fixed": "9.9.9"}]}]
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

    vulnerabilities = osv.find_vulnerabilities([COMPONENT])[COMPONENT]

    assert vulnerabilities[0].fixed_versions == ["1.0.1"]
