import pytest
from django.core.management import call_command

from envergo.moulinette.tests.factories import MoulinetteTemplateFactory

pytestmark = pytest.mark.django_db


def test_change_casse_envergo(caplog):
    "Test change_casse_envergo command."

    moulinette_template = MoulinetteTemplateFactory()
    moulinette_template.content += " EnvErgo"
    moulinette_template.save()

    call_command("change_casse_envergo")
    assert "Starting replace 'EnvErgo' by 'Envergo' in 1 templates" in [
        rec.message for rec in caplog.records
    ]
