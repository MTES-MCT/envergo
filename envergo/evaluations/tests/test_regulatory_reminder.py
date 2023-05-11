import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import RequestFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.moulinette.tests.factories import MoulinetteConfigFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def override_settings(settings):
    settings.DEFAULT_FROM_EMAIL = 'envergo-test@example.org'


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


def test_instructor_cc_field():
    req = RequestFactory(user_type=USER_TYPES.instructor, send_eval_to_sponsor=True)
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()

    assert email.cc == ["sponsor1@example.org", "sponsor2@example.org"]

    req = RequestFactory(user_type=USER_TYPES.instructor, send_eval_to_sponsor=False)
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()

    assert email.cc == []


def test_bcc_field(loire_atlantique_department):  # noqa
    req = RequestFactory()
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()
    # Default bcc field is our own address
    assert email.bcc == ['envergo-test@example.org']

    MoulinetteConfigFactory(department=loire_atlantique_department, ddtm_contact_email='ddtm_email_test@example.org')
    url = "https://example.org?lng=-2.08555&lat=47.31051"  # Somewhere in Loire-Atlantique (44), France
    req = RequestFactory(moulinette_url=url)
    eval = req.create_evaluation()
    email = eval.get_regulatory_reminder_email()
    assert email.bcc == ['envergo-test@example.org', "ddtm_email_test@example.org"]
