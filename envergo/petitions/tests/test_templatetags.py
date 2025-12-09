from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.template import Context, Template
from django.test import override_settings

from envergo.moulinette.tests.factories import DCConfigHaieFactory
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
def test_display_ds_field(mock_post):
    """Test display DS field template tag"""

    # Given a config haie with a DS display field
    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
        demarches_simplifiees_display_fields={"motivation": "Q2hhbXAtNDUzNDE0Ng=="},
    )
    # Given a petition project
    petition_project = PetitionProjectFactory()
    # Given DS dossier is available
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    # When I want to display this DS field in a template
    template_html = '{% load petitions %}{% display_ds_field "motivation" %}'
    context_data = {
        "petition_project": petition_project,
        "moulinette": petition_project.get_moulinette(),
    }
    content = Template(template_html).render(Context(context_data))
    # Then this DS field label and value are present in rendered page
    assert (
        "Pour quelle raison avez-vous le projet de détruire ces haies ou alignements d’arbres"
        in content
    )
    assert "La motivation" in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_display_empty_ds_fields(mock_post):
    """Test display DS field template tag"""

    # Given a config haie with empty DS display fields
    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
        demarches_simplifiees_display_fields={},
    )
    # Given a petition project
    petition_project = PetitionProjectFactory()
    # Given DS dossier is available
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    # When I want to display this DS field in a template
    template_html = '{% load petitions %}{% display_ds_field "motivation" %}'
    context_data = {
        "petition_project": petition_project,
        "moulinette": petition_project.get_moulinette(),
    }
    content = Template(template_html).render(Context(context_data))
    # Then this DS field label and value are not present in rendered page
    assert (
        "Pour quelle raison avez-vous le projet de détruire ces haies ou alignements d’arbres"
        not in content
    )
    assert "La motivation" not in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_display_ds_field_invalid_field_id(mock_post):
    # Given config haie with display fields not existing id
    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
        demarches_simplifiees_display_fields={"motivation": "id_imaginaire"},
    )
    # Given a petition project
    petition_project = PetitionProjectFactory()
    # Given DS dossier is available
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    # When I want to display this DS field in a template
    template_html = '{% load petitions %}{% display_ds_field "motivation" %}'
    context_data = {
        "petition_project": petition_project,
        "moulinette": petition_project.get_moulinette(),
    }
    content = Template(template_html).render(Context(context_data))
    # Then this DS field label and value are not present in rendered page
    assert (
        "Pour quelle raison avez-vous le projet de détruire ces haies ou alignements d’arbres"
        not in content
    )
    assert "La motivation" not in content


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_display_ds_field_unavailable_dossier(mock_post):
    # Given config haie with display fields not existing id
    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
        demarches_simplifiees_display_fields={"motivation": "Q2hhbXAtNDUzNDE0Ng=="},
    )
    # Given a petition project
    petition_project = PetitionProjectFactory()
    # Given DS dossier is not available
    petition_project.demarches_simplifiees_raw_dossier = None
    mock_post.return_value = {"data": {"weirdely_formatted": "response"}}

    # When I want to display this DS field in a template
    template_html = '{% load petitions %}{% display_ds_field "motivation" %}'
    context_data = {
        "petition_project": petition_project,
        "moulinette": petition_project.get_moulinette(),
    }
    content = Template(template_html).render(Context(context_data))
    # Then template is rendered without any error but no DS field is in rendered page
    assert (
        "Pour quelle raison avez-vous le projet de détruire ces haies ou alignements d’arbres"
        not in content
    )
    assert "La motivation" not in content
