import pytest
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import DepartmentFactory
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def haie_site(settings):
    settings.ENVERGO_HAIE_DOMAIN = "haie.testserver"
    return SiteFactory(domain="haie.testserver", name="haie.testserver")


@pytest.fixture
def department(haie_site):
    return DepartmentFactory(department="44")


@pytest.fixture
def haie_user(haie_site):
    return UserFactory(is_haie_user=True)


def admin_post_data(user, **overrides):
    """Build a minimal valid POST payload for the user admin change form."""
    data = {
        "email": user.email,
        "password": user.password,
        "name": user.name,
        "departments": [],
        "groups": [],
        "followed_petition_projects": [],
        "_save": "Save",
        "invitation_tokens-TOTAL_FORMS": 0,
        "invitation_tokens-INITIAL_FORMS": 0,
        "invitation_tokens-MIN_NUM_FORMS": 0,
        "invitation_tokens-MAX_NUM_FORMS": 1000,
    }

    if user.access_haie:
        data["access_haie"] = "on"
    if user.access_amenagement:
        data["access_amenagement"] = "on"
    if user.is_active:
        data["is_active"] = "on"
    if user.is_staff:
        data["is_staff"] = "on"
    if user.is_superuser:
        data["is_superuser"] = "on"
    if user.is_instructor:
        data["is_instructor"] = "on"
    data.update(overrides)
    return data


def test_adding_department_to_haie_user_sends_email(
    client, admin_user, haie_user, department
):
    """Assigning a department to a haie user triggers a rights update email."""
    client.force_login(admin_user)
    url = reverse("admin:users_user_change", args=[haie_user.pk])

    data = admin_post_data(haie_user, departments=[department.pk])
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(url, data=data)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [haie_user.email]
    assert "Attribution de droits" in mail.outbox[0].subject


def test_activating_instructor_right_sends_email(
    client, admin_user, haie_user, department
):
    """Setting is_instructor=True on a haie user with a department triggers a rights update email."""
    haie_user.departments.add(department)
    client.force_login(admin_user)
    url = reverse("admin:users_user_change", args=[haie_user.pk])

    data = admin_post_data(haie_user, is_instructor="on", departments=[department.pk])
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(url, data=data)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert (
        "Votre compte sur le portail du guichet unique de la haie a été validé."
        in email.body
    )
    assert "droits de modification" in email.body


def test_no_email_when_no_rights_changed(client, admin_user, haie_user, department):
    """Saving a haie user without changing rights does not send an email."""
    haie_user.departments.add(department)
    client.force_login(admin_user)
    url = reverse("admin:users_user_change", args=[haie_user.pk])

    data = admin_post_data(haie_user, departments=[department.pk])
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(url, data=data)

    assert len(mail.outbox) == 0


def test_no_email_when_user_has_no_departments(client, admin_user, haie_user):
    """Saving a haie user with no departments does not send an email, even if is_instructor changes."""
    client.force_login(admin_user)
    url = reverse("admin:users_user_change", args=[haie_user.pk])

    data = admin_post_data(haie_user, is_instructor="on")
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(url, data=data)

    assert len(mail.outbox) == 0


def test_no_email_for_non_haie_user(client, admin_user, department):
    """Changing departments of a non-haie user does not send an email."""
    amenagement_user = UserFactory(is_envergo_user=True)
    client.force_login(admin_user)
    url = reverse("admin:users_user_change", args=[amenagement_user.pk])

    data = admin_post_data(amenagement_user, departments=[department.pk])
    with TestCase.captureOnCommitCallbacks(execute=True):
        client.post(url, data=data)

    assert len(mail.outbox) == 0
