import pytest

from envergo.geodata.tests.factories import DepartmentFactory
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
)
from envergo.users.backends import AuthBackend
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


def test_admin_can_always_authenticate(admin_user):
    auth_backend = AuthBackend()
    assert auth_backend.user_can_authenticate(admin_user)


def test_haie_user_can_authenticate_only_on_haie(haie_user):
    auth_backend = AuthBackend()
    auth_backend.site_literal = "haie"
    assert auth_backend.user_can_authenticate(haie_user)

    auth_backend.site_literal = "amenagement"
    assert not auth_backend.user_can_authenticate(haie_user)


def test_amenagement_user_can_authenticate_only_on_amenagement(amenagement_user):
    auth_backend = AuthBackend()
    auth_backend.site_literal = "haie"
    assert not auth_backend.user_can_authenticate(amenagement_user)

    auth_backend.site_literal = "amenagement"
    assert auth_backend.user_can_authenticate(amenagement_user)


VIEW_PERM = "petitions.view_petitionproject"
CHANGE_PERM = "petitions.change_petitionproject"


def test_petition_project_object_permissions(haie_user, admin_user):
    """Object-level has_perm exposes the project's view/change permissions per role."""
    dept = DepartmentFactory(department="44")
    other_dept = DepartmentFactory(department="35")
    project = PetitionProjectFactory(department=dept)

    # Coordinator on the project's department: can view AND change.
    coordinator = UserFactory(is_haie_coordinator=True)
    coordinator.departments.add(dept)

    # Coordinator on another department: no access at all on this project.
    other_coordinator = UserFactory(is_haie_coordinator=True)
    other_coordinator.departments.add(other_dept)

    # Consulted instructor (department access, not coordinator): view only.
    instructor = UserFactory(is_haie_user=True)
    instructor.departments.add(dept)

    # Invited on the dossier through a token: view only.
    invited = UserFactory(is_haie_user=True)
    InvitationTokenFactory(user=invited, petition_project=project)

    # Superuser: everything (through the standard ModelBackend).
    assert admin_user.has_perm(VIEW_PERM, project)
    assert admin_user.has_perm(CHANGE_PERM, project)

    assert coordinator.has_perm(VIEW_PERM, project)
    assert coordinator.has_perm(CHANGE_PERM, project)

    assert instructor.has_perm(VIEW_PERM, project)
    assert not instructor.has_perm(CHANGE_PERM, project)

    assert invited.has_perm(VIEW_PERM, project)
    assert not invited.has_perm(CHANGE_PERM, project)

    # Guest (authenticated, no dept/token) and wrong-department coordinator: nothing.
    assert not haie_user.has_perm(VIEW_PERM, project)
    assert not haie_user.has_perm(CHANGE_PERM, project)
    assert not other_coordinator.has_perm(VIEW_PERM, project)
    assert not other_coordinator.has_perm(CHANGE_PERM, project)


def test_petition_project_perm_without_obj_falls_back_to_model_backend(haie_user):
    """Without an object, the model-level permission is not granted to regular users.

    Guards the invariant that object access is decided solely by our backend: the
    model-level view/change permissions must never leak (they are not assigned to
    anyone).
    """
    coordinator = UserFactory(is_haie_coordinator=True)
    assert not coordinator.has_perm(CHANGE_PERM)
    assert not coordinator.has_perm(VIEW_PERM)
    assert not haie_user.has_perm(CHANGE_PERM)
