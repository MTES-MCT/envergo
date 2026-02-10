import pytest

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


def test_user_is_involved(haie_user, haie_user_44, haie_instructor_44, admin_user):
    """Test when user is involved in GUH"""
    # AS superuser, user is involved in GUH
    assert admin_user.is_involved_in_guh()
    # AS instructor on 44, user is involved in GUH
    assert haie_instructor_44.is_involved_in_guh()
    # AS basic user on 44, user is involved in GUH
    assert haie_user_44.is_involved_in_guh()
    # AS basic user with no rights, user is involved in GUH
    assert not haie_user.is_involved_in_guh()
    # WHEN basic user has a token
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    # THEN this user is involved in GUH
    InvitationTokenFactory(user=haie_user, petition_project=petition_project)
    assert haie_user.is_involved_in_guh()


def test_get_unique_hash(haie_user, haie_user_44):
    """Test get_unique_hash method"""
    assert haie_user_44.get_unique_hash() != haie_user.get_unique_hash()
