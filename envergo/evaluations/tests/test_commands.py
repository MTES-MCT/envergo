from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from envergo.evaluations.tests.factories import RequestFactory, RequestFileFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def time_10min_ago():
    return localtime() - timedelta(minutes=10)


@pytest.fixture
def time_20min_ago():
    return localtime() - timedelta(minutes=20)


@pytest.fixture
def time_45min_ago():
    return localtime() - timedelta(minutes=45)


@pytest.fixture
def time_1h30_ago():
    return localtime() - timedelta(minutes=90)


@pytest.fixture
def time_3h_ago():
    return localtime() - timedelta(hours=3)


@patch("envergo.evaluations.management.commands.new_files_admin_alert.notify")
def test_new_files_admin_alert_with_new_requests(mock_notify):
    """When a request was just created, no alert is sent."""
    request = RequestFactory()
    RequestFileFactory(request=request)
    call_command("new_files_admin_alert")

    mock_notify.assert_not_called()


@patch("envergo.evaluations.management.commands.new_files_admin_alert.notify")
def test_new_files_admin_alert_with_new_file_lt_1hr_ago(
    mock_notify, time_3h_ago, time_45min_ago
):
    """When a file was just uploaded, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_45min_ago)
    call_command("new_files_admin_alert")

    mock_notify.assert_not_called()


@patch("envergo.evaluations.management.commands.new_files_admin_alert.notify")
def test_new_files_admin_alert_with_new_file_gt_1hr_ago(
    mock_notify, time_3h_ago, time_1h30_ago
):
    """When a file was uploaded recently than 1hr, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_1h30_ago)
    call_command("new_files_admin_alert")

    mock_notify.assert_called_once()


@patch("envergo.evaluations.management.commands.new_files_admin_alert.notify")
def test_new_files_admin_alert_with_old_file(mock_notify, time_3h_ago):
    """When a file was uploaded a while ago, no alert is sent."""

    request = RequestFactory(created_at=time_3h_ago)
    RequestFileFactory(request=request, uploaded_at=time_3h_ago)
    call_command("new_files_admin_alert")

    mock_notify.assert_not_called()


def test_new_files_user_alert_with_new_requests(mailoutbox):
    """When a request was just created, no alert is sent to user."""
    request = RequestFactory()
    RequestFileFactory(request=request)
    call_command("new_files_user_alert")

    assert len(mailoutbox) == 0


def test_new_files_user_alert_with_new_file_lt_15min_ago(
    mailoutbox, time_1h30_ago, time_10min_ago
):
    """When a file was just uploaded, no alert is sent."""

    request = RequestFactory(created_at=time_1h30_ago)
    RequestFileFactory(request=request, uploaded_at=time_10min_ago)
    call_command("new_files_user_alert")

    assert len(mailoutbox) == 0


def test_new_files_user_alert_with_new_file_gt_15min_ago(
    mailoutbox, time_1h30_ago, time_20min_ago
):
    """When a file was uploaded more than 15min ago, an alert is sent."""

    request = RequestFactory(created_at=time_1h30_ago)
    RequestFileFactory(request=request, uploaded_at=time_20min_ago)
    call_command("new_files_user_alert")

    assert len(mailoutbox) == 1


def test_new_files_user_alert_with_new_file_gt_30min_ago(
    mailoutbox, time_1h30_ago, time_45min_ago
):
    """File uploaded more than 30min ago, it's too late, no alert is sent."""

    request = RequestFactory(created_at=time_1h30_ago)
    RequestFileFactory(request=request, uploaded_at=time_45min_ago)
    call_command("new_files_user_alert")

    assert len(mailoutbox) == 0


def test_new_files_user_alert_recipient(mailoutbox, time_1h30_ago, time_20min_ago):
    """The mail is sent to the right recipients."""

    request = RequestFactory(user_type="instructor", created_at=time_1h30_ago)
    RequestFileFactory(request=request, uploaded_at=time_20min_ago)
    call_command("new_files_user_alert")

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == ["instructor@example.org"]

    request.user_type = "petitioner"
    request.save()
    call_command("new_files_user_alert")
    assert len(mailoutbox) == 2
    email = mailoutbox[1]
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
