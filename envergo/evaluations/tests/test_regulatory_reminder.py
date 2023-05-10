import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import RequestFactory

pytestmark = pytest.mark.django_db


def test_instructor_to_field():
    req = RequestFactory(user_type=USER_TYPES.instructor)
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()

    assert email.to == ["instructor@example.org"]


def test_petitioner_to_field():
    req = RequestFactory(user_type=USER_TYPES.petitioner)
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()

    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
