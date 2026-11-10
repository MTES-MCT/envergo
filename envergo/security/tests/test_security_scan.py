from dataclasses import replace
from unittest.mock import patch

import pytest
from django.core.management import call_command

from envergo.security.inventory import Component, Ecosystem
from envergo.security.models import Vulnerability
from envergo.security.osv import Finding

pytestmark = pytest.mark.django_db

COMPONENT = Component("some-package", "1.0.0", Ecosystem.PYPI)
KNOWN_FLAW = Finding("GHSA-known", "Known flaw", "high", [])
NEW_FLAW = Finding("GHSA-new", "New flaw", "low", ["1.0.1"])
CLOSED_FLAW = Finding("GHSA-closed", "Closed flaw", "low", [])
HIGH_FLAW = Finding("GHSA-high", "High flaw", "high", [])
LOW_FLAW = Finding("GHSA-low", "Low flaw", "low", [])


@pytest.fixture(autouse=True)
def scan_enabled(settings):
    """Turn on the scan, which is off by default."""
    settings.SECURITY_SCAN_ENABLED = True


def run_scan(findings):
    """Run the command with OSV reporting these findings on `COMPONENT`."""
    findings_by_component = {COMPONENT: findings}
    with (
        patch(
            "envergo.security.management.commands.security_scan.read_components",
            return_value=[COMPONENT],
        ),
        patch(
            "envergo.security.management.commands.security_scan.find_vulnerabilities",
            return_value=findings_by_component,
        ),
    ):
        call_command("security_scan")


def test_scan_syncs_open_vulnerabilities():
    """A new flaw adds a row, a known one keeps its date, a closed one is deleted."""
    run_scan([KNOWN_FLAW, CLOSED_FLAW])
    known_row = Vulnerability.objects.get(vulnerability_id=KNOWN_FLAW.id)

    known_flaw_with_fix = replace(KNOWN_FLAW, fixed_versions=["1.0.2"])
    run_scan([known_flaw_with_fix, NEW_FLAW])

    open_ids = Vulnerability.objects.values_list("vulnerability_id", flat=True)
    assert set(open_ids) == {KNOWN_FLAW.id, NEW_FLAW.id}

    updated_known_row = Vulnerability.objects.get(vulnerability_id=KNOWN_FLAW.id)
    assert updated_known_row.detected_at == known_row.detected_at
    assert updated_known_row.fixed_versions == ["1.0.2"]


def test_scan_alerts_only_on_new_important_vulnerabilities(settings):
    """Only a newly found high flaw posts, listing it alone with the open total."""
    settings.TCHAP_ROOM_ID_SECURITY = "!security:example.org"

    with patch("envergo.utils.tchap.send") as send:
        run_scan([LOW_FLAW])
        assert not send.called

        run_scan([LOW_FLAW, HIGH_FLAW])

    room_id, message = send.call_args.args
    assert send.call_count == 1
    assert room_id == "!security:example.org"
    assert HIGH_FLAW.id in message
    assert LOW_FLAW.id not in message
    assert "Vulnérabilités ouvertes au total : 2" in message
