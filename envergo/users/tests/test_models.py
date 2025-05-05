import pytest

from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_is_instructor(instructor_haie_user, haie_user, amenagement_user):
    """Test if user is instructor"""
    unactive_user = UserFactory(
        is_active=False,
        access_amenagement=False,
        access_haie=True,
        is_confirmed_by_admin=True,
    )
    assert unactive_user.is_instructor is False
    assert amenagement_user.is_instructor is False
    assert haie_user.is_instructor is False
    assert instructor_haie_user.is_instructor is True
