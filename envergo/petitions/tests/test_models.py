import factory
import pytest

from envergo.geodata.tests.factories import Department34Factory
from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import (
    PetitionProject34Factory,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department.department == "44"


def test_following_instructors_on_petition_project(
    invited_haie_user_44, instructor_haie_user_44, admin_user
):
    """Test following instructors on petition project
    - follows project
    - is a member of project department
    - is instructor
    - is not superuser
    """
    DCConfigHaieFactory()
    DCConfigHaieFactory(department=factory.SubFactory(Department34Factory))
    # GIVEN a petition project in 44 followed by invited user, instructor user and admin user
    petition_project = PetitionProjectFactory.create()
    petition_project.followed_by.add(invited_haie_user_44)
    petition_project.followed_by.add(instructor_haie_user_44)
    petition_project.followed_by.add(admin_user)
    # WHEN I get followed by instructor list
    following_instructors = petition_project.get_following_instructors()
    # THEN only instructor user is listed
    assert following_instructors.count() == 1
    assert following_instructors.first() == instructor_haie_user_44

    # GIVEN a petition project in 34 followed by users in 44
    project_34 = PetitionProject34Factory.create()
    project_34.followed_by.add(invited_haie_user_44)
    project_34.followed_by.add(instructor_haie_user_44)
    project_34.followed_by.add(admin_user)
    # WHEN I get followed by instructor list
    following_instructors = project_34.get_following_instructors()
    # THEN no instructor user are listed
    assert following_instructors.count() == 0
