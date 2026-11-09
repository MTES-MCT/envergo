from unittest.mock import patch

import pytest
from django.urls import reverse

from envergo.security.inventory import Component
from envergo.security.tests.factories import VulnerabilityFactory

pytestmark = pytest.mark.django_db

OTHER_COMPONENT = Component("other-package", "2.0.0", "npm")


def test_dashboard_sorts_by_severity_and_lists_other_components(admin_client, site):
    """The most urgent vulnerability comes first, and clean components are listed apart."""
    low = VulnerabilityFactory(vulnerability_id="GHSA-low", severity="low")
    VulnerabilityFactory(vulnerability_id="GHSA-critical", severity="critical")
    inventory = [low.component, OTHER_COMPONENT]

    with patch("envergo.security.admin.read_components", return_value=inventory):
        response = admin_client.get(reverse("admin:security_vulnerability_changelist"))

    vulnerabilities = response.context["vulnerabilities"]
    assert [v.vulnerability_id for v in vulnerabilities] == [
        "GHSA-critical",
        "GHSA-low",
    ]
    assert response.context["other_components"] == [OTHER_COMPONENT]
