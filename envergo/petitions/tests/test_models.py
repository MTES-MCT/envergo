import pytest

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department.department == "44"
