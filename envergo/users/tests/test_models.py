from unittest.mock import patch

import pytest

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
)
from envergo.users.models import GuhRole

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
    # THEN this user has instruction access
    InvitationTokenFactory(user=haie_user, petition_project=petition_project)
    assert haie_user.has_instruction_access
    # AS Anonymous user, no instruction access
    with patch.object(type(haie_user), "is_authenticated", False):
        assert not haie_user.has_instruction_access


def test_user_get_guh_role(haie_user, haie_user_44, haie_coordinator_44, admin_user):
    """get_guh_role returns the business typology for each role."""
    assert admin_user.get_guh_role() == GuhRole.ADMINISTRATOR
    assert haie_coordinator_44.get_guh_role() == GuhRole.COORDINATOR
    # dept access but not coordinator -> consulted instructor
    assert haie_user_44.get_guh_role() == GuhRole.INSTRUCTOR
    # authenticated, no dept/token -> guest
    assert haie_user.get_guh_role() == GuhRole.GUEST

    # unauthenticated -> anonymous
    with patch.object(type(haie_user), "is_authenticated", False):
        assert haie_user.get_guh_role() == GuhRole.ANONYMOUS


def test_get_unique_hash(haie_user, haie_user_44):
    """Test get_unique_hash method"""
    assert haie_user_44.get_unique_hash() != haie_user.get_unique_hash()
