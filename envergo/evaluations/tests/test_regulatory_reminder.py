import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import RequestFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.moulinette.tests.factories import MoulinetteConfigFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def override_settings(settings):
    settings.DEFAULT_FROM_EMAIL = "envergo-test@example.org"


def test_instructor_to_field(rf):
    evalreq = RequestFactory(user_type=USER_TYPES.instructor)
    eval = evalreq.create_evaluation()
    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)

    assert email.to == ["instructor@example.org"]


def test_petitioner_to_field(rf):
    evalreq = RequestFactory(user_type=USER_TYPES.petitioner)
    eval = evalreq.create_evaluation()
    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)

    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]


def test_instructor_cc_field(rf):
    evalreq = RequestFactory(user_type=USER_TYPES.instructor, send_eval_to_sponsor=True)
    eval = evalreq.create_evaluation()
    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)

    assert email.cc == ["sponsor1@example.org", "sponsor2@example.org"]

    evalreq = RequestFactory(
        user_type=USER_TYPES.instructor, send_eval_to_sponsor=False
    )
    eval = evalreq.create_evaluation()
    email = eval.get_regulatory_reminder_email(req)

    assert email.cc == []


def test_bcc_field(rf, loire_atlantique_department):  # noqa
    evalreq = RequestFactory()
    eval = evalreq.create_evaluation()
    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)
    # Default bcc field is our own address
    assert email.bcc == ["envergo-test@example.org"]

    MoulinetteConfigFactory(
        department=loire_atlantique_department,
        ddtm_contact_email="ddtm_email_test@example.org",
    )
    url = "https://example.org?lng=-2.08555&lat=47.31051"  # Somewhere in Loire-Atlantique (44), France
    evalreq = RequestFactory(moulinette_url=url)
    eval = evalreq.create_evaluation()
    email = eval.get_regulatory_reminder_email(req)
    assert email.bcc == ["envergo-test@example.org", "ddtm_email_test@example.org"]
