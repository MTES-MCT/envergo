import pytest

from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_users_instructor_or_invited(
    user,
    haie_user,
    inactive_haie_user_44,
    invited_haie_user_44,
    instructor_haie_user_44,
):
    """Test is_instructor_guh, is_invited_guh methods on User model"""

    # Given haie_user, with no department and `is_instructor` False
    # Then this user is not invited_guh nor instructor_guh
    assert haie_user.is_invited_guh() is False
    assert haie_user.is_instructor_guh() is False

    # When a haie user is created without right to this department and `is_instructor` True
    haie_user_no_department = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
        is_instructor=True,
    )
    # Then this user is not invited_guh nor instructor_guh
    assert haie_user_no_department.is_invited_guh() is False
    assert haie_user_no_department.is_instructor_guh() is False

    # Given invited_haie_user_44, with right to department 44 and `is_instructor` False
    # Then this user is only invited_guh
    assert invited_haie_user_44.is_invited_guh() is True
    assert invited_haie_user_44.is_instructor_guh() is False

    # Given instructor_haie_user_44, with right to department 44 and `is_instructor` True
    # Then this user is instructor_guh
    assert instructor_haie_user_44.is_invited_guh() is False
    assert instructor_haie_user_44.is_instructor_guh() is True
