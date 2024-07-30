from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from envergo.evaluations.tests.factories import RequestFactory, RequestFileFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def time_45min_ago():
    return localtime() - timedelta(minutes=45)


@pytest.fixture
def time_1h30_ago():
    return localtime() - timedelta(minutes=90)


@pytest.fixture
def time_3h_ago():
    return localtime() - timedelta(hours=3)


@patch("envergo.evaluations.management.commands.new_files_alert.notify")
def test_new_files_alert_with_new_requests(mock_notify):
    """When a request was just created, no alert is sent."""
    request = RequestFactory()
    RequestFileFactory(request=request)
    call_command("new_files_alert")

    mock_notify.assert_not_called()


@patch("envergo.evaluations.management.commands.new_files_alert.notify")
def test_new_files_alert_with_new_file_lt_1hr_ago(
    mock_notify, time_3h_ago, time_45min_ago
):
    """When a file was just uploaded, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_45min_ago)
    call_command("new_files_alert")

    mock_notify.assert_not_called()


@patch("envergo.evaluations.management.commands.new_files_alert.notify")
def test_new_files_alert_with_new_file_gt_1hr_ago(
    mock_notify, time_3h_ago, time_1h30_ago
):
    """When a file was uploaded recently than 1hr, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_1h30_ago)
    call_command("new_files_alert")

    mock_notify.assert_called_once()


@patch("envergo.evaluations.management.commands.new_files_alert.notify")
def test_new_files_alert_with_old_file(mock_notify, time_3h_ago):
    """When a file was uploaded a while ago, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_3h_ago)
    call_command("new_files_alert")

    mock_notify.assert_not_called()
