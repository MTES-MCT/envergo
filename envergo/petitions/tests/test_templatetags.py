from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.template import Context, Template
from django.test import override_settings

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.templatetags.petitions import display_due_date
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    GET_DOSSIER_FAKE_RESPONSE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


def test_display_choice():
    today = datetime.now()

    ten_days_ago = (today - timedelta(days=10)).date()
    one_day_ago = (today - timedelta(days=1)).date()
    in_one_day = (today + timedelta(days=1)).date()
    in_five_days = (today + timedelta(days=5)).date()
    in_ten_days = (today + timedelta(days=10)).date()

    result = display_due_date(in_ten_days)
    assert "fr-icon-timer-line" in result
    assert "10 jours restants" in result

    result = display_due_date(in_five_days)
    assert "fr-icon-hourglass-2-fill" in result
    assert "5 jours restants" in result

    result = display_due_date(in_one_day)
    assert "fr-icon-hourglass-2-fill" in result
    assert "1 jour restant" in result

    result = display_due_date(today.date())
    assert "fr-icon-hourglass-2-fill" in result
    assert "0 jour restant" in result

    result = display_due_date(one_day_ago)
    assert "fr-icon-warning-fill" in result
    assert "Dépassée depuis 1 jour" in result

    result = display_due_date(ten_days_ago)
    assert "fr-icon-warning-fill" in result
    assert "Dépassée depuis 10 jours" in result


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_display_ds_field(mock_post, client):
    """Test display DS field template tag"""

    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
        demarches_simplifiees_display_fields={"motivation": "Q2hhbXAtNDUzNDE0Ng=="},
    )
    petition_project = PetitionProjectFactory.create()

    template_html = '{% load petitions %}{% display_ds_field "motivation" %}'
    context_data = {
        "petition_project": petition_project,
        "moulinette": petition_project.get_moulinette(),
    }
    content = Template(template_html).render(Context(context_data))

    assert (
        "Pour quelle raison avez-vous le projet de détruire ces haies ou alignements d’arbres"
        in content
    )
