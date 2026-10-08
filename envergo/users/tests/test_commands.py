from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from envergo.users.models import User
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def three_days_ago():
    return localtime() - timedelta(days=3)


def test_delete_unactivated_accounts_deletes_old_unactivated_account(three_days_ago):
    UserFactory(is_active=False, last_login=None, date_joined=three_days_ago)

    call_command("delete_unactivated_accounts")

    assert not User.objects.exists()


def test_delete_unactivated_accounts_keeps_recent_signup():
    """A recent signup can still be activated."""
    UserFactory(is_active=False, last_login=None, date_joined=localtime())

    call_command("delete_unactivated_accounts")

    assert User.objects.count() == 1


def test_delete_unactivated_accounts_keeps_deactivated_account(three_days_ago):
    """An account that has logged in was deactivated on purpose."""
    UserFactory(is_active=False, last_login=three_days_ago, date_joined=three_days_ago)

    call_command("delete_unactivated_accounts")

    assert User.objects.count() == 1


def test_delete_unactivated_accounts_keeps_active_account(three_days_ago):
    """Admin-created accounts are active before their first login."""
    UserFactory(is_active=True, last_login=None, date_joined=three_days_ago)

    call_command("delete_unactivated_accounts")

    assert User.objects.count() == 1
