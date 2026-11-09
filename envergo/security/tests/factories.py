from factory import Sequence
from factory.django import DjangoModelFactory

from envergo.security.models import Vulnerability


class VulnerabilityFactory(DjangoModelFactory):
    """An open vulnerability, by default all on the same library."""

    component_name = "vulnerable-package"
    component_version = "1.0.0"
    ecosystem = "PyPI"
    vulnerability_id = Sequence(lambda n: f"GHSA-{n}")
    severity = "high"

    class Meta:
        model = Vulnerability
