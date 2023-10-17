from unittest.mock import MagicMock
from urllib.parse import urlencode

import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import EvaluationFactory
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
    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=False,
    )
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" in body


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is checked
    """
    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "soumis"

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]
    assert email.bcc == ["ddtm_email_test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [800])
def test_instructor_transmit_action_requise(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "action requise"
    - the "send to sponsor" checkbox is checked
    """
    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "action_requise"

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [50])
def test_instructor_transmit_non_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "non soumis"
    - the "send to sponsor" checkbox is checked
    """
    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=True,
    )
    moulinette = eval.get_moulinette()
    assert moulinette.loi_sur_leau.zone_humide.result == "non_soumis"

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_petitioner(rf, moulinette_url):
    eval = EvaluationFactory(
        user_type=USER_TYPES.petitioner,
        moulinette_url=moulinette_url,
        send_eval_to_sponsor=False,
    )
    req = rf.get("/")
    email = eval.get_evaluation_email(req)

    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body


def fake_moulinette(url, lse, n2000, evalenv, sage):
    """Create a moulinette with custom regulation results."""
    lse = MagicMock(result=lse)
    n2000 = MagicMock(result=n2000)
    evalenv = MagicMock(result=evalenv)
    sage = MagicMock(result=sage)
    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=url,
        send_eval_to_sponsor=True,
    )
    moulinette = eval.get_moulinette()
    moulinette.regulations = [lse, n2000, evalenv, sage]
    return moulinette


@pytest.mark.parametrize("footprint", [1200])
def test_moulinette_global_result(moulinette_url):
    expected_results = [
        (("soumis", "non_soumis", "non_concerne", "interdit"), "interdit"),
        (("soumis", "soumis", "action_requise", "interdit"), "interdit"),
        (("soumis", "action_requise", "non_concerne", "non_disponible"), "soumis"),
        (("soumis", "non_soumis", "non_soumis", "non_soumis"), "soumis"),
        (("non_soumis", "non_soumis", "systematique", "non_soumis"), "soumis"),
        (("non_soumis", "non_soumis", "cas_par_cas", "non_soumis"), "soumis"),
        (
            ("non_soumis", "non_soumis", "action_requise", "non_soumis"),
            "action_requise",
        ),
        (("non_soumis", "non_soumis", "non_concerne", "non_soumis"), "non_soumis"),
        (("non_soumis", "non_soumis", "non_concerne", "non_disponible"), "non_soumis"),
    ]

    for results, expected_result in expected_results:
        moulinette = fake_moulinette(moulinette_url, *results)
        assert moulinette.result == expected_result
