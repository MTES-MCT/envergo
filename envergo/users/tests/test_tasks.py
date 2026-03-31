import pytest
from django.core import mail

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.geodata.tests.factories import DepartmentFactory
from envergo.users.tasks import send_guh_instruction_rights_update_email
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def haie_site(settings):
    settings.ENVERGO_HAIE_DOMAIN = "haie.testserver"
    return SiteFactory(domain="haie.testserver", name="haie.testserver")


@pytest.fixture
def haie_user_with_dept(haie_site):
    user = UserFactory(is_haie_user=True)
    dept = DepartmentFactory()
    user.departments.add(dept)
    return user


@pytest.fixture
def haie_instructor_with_dept(haie_site):
    user = UserFactory(is_haie_instructor=True)
    dept = DepartmentFactory()
    user.departments.add(dept)
    return user


def test_send_guh_instruction_rights_update_email_instructor_activated(
    haie_instructor_with_dept,
):
    """When instructor is newly activated, email body says account was validated."""
    user = haie_instructor_with_dept
    send_guh_instruction_rights_update_email(user.pk, is_new_instructor=True)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [user.email]
    assert "Attribution de droits" in email.subject
    assert (
        "Votre compte sur le portail du guichet unique de la haie a été validé."
        in email.body
    )
    assert "droits de modification" in email.body
    assert "service coordonnateur" in email.body
    assert "/projet/liste" in email.body


def test_send_guh_instruction_rights_update_email_rights_modified(haie_user_with_dept):
    """When only departments change, email body says rights were modified."""
    user = haie_user_with_dept
    send_guh_instruction_rights_update_email(user.pk, is_new_instructor=False)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == [user.email]
    assert "Des droits ont été modifiés" in email.body
    assert "droits de lecture" in email.body
    assert "service consulté" in email.body


def test_send_guh_instruction_rights_update_email_lists_departments(haie_site):
    """All user departments are listed in the email."""
    user = UserFactory(is_haie_user=True)
    dept1 = DepartmentFactory(department="44")
    dept2 = DepartmentFactory(department="35")
    user.departments.set([dept1, dept2])

    send_guh_instruction_rights_update_email(user.pk, is_new_instructor=False)

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert dept1.get_department_display() in body
    assert dept2.get_department_display() in body


def test_send_guh_instruction_rights_update_email_missing_user(haie_site):
    """Task is a no-op when user does not exist."""
    send_guh_instruction_rights_update_email(99999, is_new_instructor=False)
    assert len(mail.outbox) == 0


def test_send_guh_instruction_rights_update_email_missing_site(settings):
    """Task is a no-op when haie site does not exist."""
    settings.ENVERGO_HAIE_DOMAIN = "nonexistent.testserver"
    user = UserFactory(is_haie_user=True)
    send_guh_instruction_rights_update_email(user.pk, is_new_instructor=False)
    assert len(mail.outbox) == 0
