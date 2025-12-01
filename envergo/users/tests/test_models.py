import pytest

from envergo.geodata.tests.factories import DepartmentFactory
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_users_instructor_or_invited(
    user, haie_user, instructor_haie_user_44, inactive_haie_user_44
):
    """Test is_instructor_guh, is_invited_guh methods on User model"""
    # Given a Department
    department_44 = DepartmentFactory.create()

    # When a haie user is created without right to this department and `is_instructor_for_departments` True
    haie_user_no_department = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
        is_instructor_for_departments=True,
    )
    # Then this user is not invited_guh nor instructor_guh
    assert haie_user_no_department.is_invited_guh() is False
    assert haie_user_no_department.is_instructor_guh() is False

    # When a haie user is created with right to this department and `is_instructor_for_departments` False
    instructor_haie_user_44_not_instructor = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
        is_instructor_for_departments=False,
    )
    instructor_haie_user_44_not_instructor.departments.add(department_44)
    # Then this user is only invited_guh
    assert instructor_haie_user_44_not_instructor.is_invited_guh() is True
    assert instructor_haie_user_44_not_instructor.is_instructor_guh() is False

    # When a haie user is created with right to this department and `is_instructor_for_departments` True
    instructor_haie_user_44_instructor = UserFactory(
        is_active=True,
        access_amenagement=False,
        access_haie=True,
        is_instructor_for_departments=True,
    )
    instructor_haie_user_44_instructor.departments.add(department_44)
    # Then this user is instructor_guh
    assert instructor_haie_user_44_instructor.is_invited_guh() is False
    assert instructor_haie_user_44_instructor.is_instructor_guh() is True
