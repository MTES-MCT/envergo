from unittest.mock import patch

import pytest

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
)
from envergo.users.models import GuhRole, User

pytestmark = pytest.mark.django_db


def test_user_has_instruction_access(
    haie_user, haie_user_44, haie_coordinator_44, admin_user
):
    """Test has_instruction_access (« instructeur au sens produit »)."""
    # AS superuser (administrator), user has instruction access
    assert admin_user.has_instruction_access
    # AS coordinator on 44, user has instruction access
    assert haie_coordinator_44.has_instruction_access
    # AS consulted instructor (dept 44, not coordinator), user has instruction access
    assert haie_user_44.has_instruction_access
    # AS basic authenticated user with no rights (guest), no instruction access
    assert not haie_user.has_instruction_access
    # WHEN basic user has a token
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    InvitationTokenFactory(user=haie_user, petition_project=petition_project)
    # THEN this user has instruction access.
    # The role is cached per instance, so a token granted after a first check is
    # only seen by the next request, i.e. a freshly loaded user.
    assert not haie_user.has_instruction_access
    assert User.objects.get(pk=haie_user.pk).has_instruction_access
    # AS Anonymous user, no instruction access
    with patch.object(User, "is_authenticated", False):
        assert not User.objects.get(pk=haie_user.pk).has_instruction_access


def test_user_guh_role(haie_user, haie_user_44, haie_coordinator_44, admin_user):
    """guh_role returns the business typology for each role."""
    assert admin_user.guh_role == GuhRole.ADMINISTRATOR
    assert haie_coordinator_44.guh_role == GuhRole.COORDINATOR
    # dept access but not coordinator -> consulted instructor
    assert haie_user_44.guh_role == GuhRole.INSTRUCTOR
    # authenticated, no dept/token -> guest
    assert haie_user.guh_role == GuhRole.GUEST

    # unauthenticated -> anonymous
    with patch.object(User, "is_authenticated", False):
        assert User.objects.get(pk=haie_user.pk).guh_role == GuhRole.ANONYMOUS


def test_user_guh_role_is_cached(haie_user_44, django_assert_num_queries):
    """guh_role is resolved once per instance."""
    assert haie_user_44.guh_role == GuhRole.INSTRUCTOR
    with django_assert_num_queries(0):
        assert haie_user_44.guh_role == GuhRole.INSTRUCTOR
        assert haie_user_44.has_instruction_access


def test_get_unique_hash(haie_user, haie_user_44):
    """Test get_unique_hash method"""
    assert haie_user_44.get_unique_hash() != haie_user.get_unique_hash()
