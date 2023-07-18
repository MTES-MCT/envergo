from urllib.parse import urlencode

import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import RequestFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map, france_zh  # noqa
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def override_settings(settings):
    settings.DEFAULT_FROM_EMAIL = "envergo-test@example.org"


@pytest.fixture(autouse=True)
def moulinette_config(france_map, france_zh, loire_atlantique_department):  # noqa
    MoulinetteConfigFactory(
        department=loire_atlantique_department,
        is_activated=True,
        ddtm_contact_email="ddtm_email_test@example.org",
    )
    regulation = RegulationFactory()
    PerimeterFactory(
        regulation=regulation,
        activation_map=france_map,
    )
    classes = [
        "envergo.moulinette.regulations.loisurleau.ZoneHumide",
        "envergo.moulinette.regulations.loisurleau.ZoneInondable",
        "envergo.moulinette.regulations.loisurleau.Ruissellement",
    ]
    for path in classes:
        CriterionFactory(
            regulation=regulation, activation_map=france_map, evaluator=path
        )


@pytest.fixture
def moulinette_url(footprint):
    params = {
        # Somewhere south of Nantes, 44
        "lat": 47.08285,
        "lng": -1.66259,
        "created_surface": footprint,
        "final_surface": footprint,
    }
    url = urlencode(params)
    return f"https://envergo.beta.gouv.fr?{url}"


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_dont_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is not checked
    """
    evalreq = RequestFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=False,
    )
    eval = evalreq.create_evaluation()
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"

    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == ["envergo-test@example.org"]

    body = email.body
    assert "À transmettre au porteur" in body


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is checked
    """
    evalreq = RequestFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    eval = evalreq.create_evaluation()
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"

    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]
    assert email.bcc == ["ddtm_email_test@example.org", "envergo-test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [800])
def test_instructor_transmit_action_requise(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "action requise"
    - the "send to sponsor" checkbox is checked
    """
    evalreq = RequestFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    eval = evalreq.create_evaluation()
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"

    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]
    assert email.bcc == ["envergo-test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [50])
def test_instructor_transmit_non_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "non soumis"
    - the "send to sponsor" checkbox is checked
    """
    evalreq = RequestFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    eval = evalreq.create_evaluation()
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"

    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == ["envergo-test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_petitioner(rf, moulinette_url):
    evalreq = RequestFactory(
        user_type=USER_TYPES.petitioner,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=False,
    )
    eval = evalreq.create_evaluation()
    req = rf.get("/")
    email = eval.get_regulatory_reminder_email(req)

    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == []
    assert email.bcc == ["envergo-test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body
