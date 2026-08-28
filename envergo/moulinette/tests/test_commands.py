from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteTemplateFactory,
)

pytestmark = pytest.mark.django_db


@patch("envergo.utils.mattermost.notify")
def test_dossier_submission_admin_alert(mock_notify):
    """Test obsolete moulinette template admin alert"""
    criterion = CriterionFactory()
    # GIVEN a template with no existing template key
    MoulinetteTemplateFactory()
    MoulinetteTemplateFactory(criterion=criterion, config=None)
    # WHEN command is called
    call_command("obsolete_moulinette_template_admin_alert")
    # THEN notify should be called twice
    assert mock_notify.call_count == 2
    # AND first message is related to config
    args, _ = mock_notify.call_args_list[0]
    assert 'La config Aménagement du département ["Loire-Atlantique (44)"]' in args[0]
    assert " référence un gabarit moulinette obsolète" in args[0]
    assert "amenagement" in args[1]
    # AND second message is related to config
    args, _ = mock_notify.call_args_list[1]
    assert 'Le critère ["Zone humide"]' in args[0]
    assert " référence un gabarit moulinette obsolète" in args[0]
    assert "amenagement" in args[1]


@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="")
@patch("envergo.utils.mattermost.notify")
def test_dossier_submission_admin_alert_amenagement_domain_not_configured(
    mock_notify,
):
    """Test obsolete moulinette template admin alert"""

    # GIVEN a template with no existing template key
    MoulinetteTemplateFactory()
    # WHEN command is called
    call_command("obsolete_moulinette_template_admin_alert")
    # THEN notify should not be called because no amenagement domain is set
    mock_notify.assert_not_called()
