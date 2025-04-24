import pytest

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    ConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department_code == "44"
