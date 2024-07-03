from unittest.mock import Mock, call, patch
from urllib.parse import urlencode

import pytest

from envergo.evaluations.models import Evaluation, Request
from envergo.evaluations.tests.factories import EvaluationFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    MoulinetteConfigFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def moulinette_config(france_map, loire_atlantique_department):  # noqa
    MoulinetteConfigFactory(
        department=loire_atlantique_department,
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )
    regulation = RegulationFactory(regulation="loi_sur_leau")
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
def test_call_to_action_action(moulinette_url):
    evaluation = EvaluationFactory(moulinette_url=moulinette_url)
    moulinette = evaluation.get_moulinette()
    regulation = RegulationFactory()

    assert not evaluation.is_icpe

    moulinette.regulations = [Mock(regulation, wraps=regulation, result="non_soumis")]
    assert moulinette.result == "non_soumis"
    assert not evaluation.is_eligible_to_self_declaration()

    moulinette.regulations = [
        Mock(regulation, wraps=regulation, result="action_requise")
    ]
    assert moulinette.result == "action_requise"
    assert evaluation.is_eligible_to_self_declaration()

    moulinette.regulations = [Mock(regulation, wraps=regulation, result="soumis")]
    assert moulinette.result == "soumis"
    assert evaluation.is_eligible_to_self_declaration()

    moulinette.regulations = [Mock(regulation, wraps=regulation, result="interdit")]
    assert moulinette.result == "interdit"
    assert evaluation.is_eligible_to_self_declaration()

    evaluation.is_icpe = True
    evaluation.save()
    assert not evaluation.is_eligible_to_self_declaration()


def test_prevent_storing_project_owner_details_when_we_should_not_send_him_the_eval():
    request = Request(
        address="123 rue de la Paix 75000 Paris",
        project_owner_phone="+33612345678",
        project_owner_emails=["test@test.com"],
        send_eval_to_project_owner=False,
    )
    request.save()
    request.refresh_from_db()
    assert not request.project_owner_phone
    assert not request.project_owner_emails

    request = Request(
        address="123 rue de la Paix 75000 Paris",
        project_owner_phone="+33612345678",
        project_owner_emails=["test@test.com"],
        send_eval_to_project_owner=True,
    )
    request.save()
    request.refresh_from_db()
    assert request.project_owner_phone == "+33612345678"
    assert request.project_owner_emails == ["test@test.com"]


def test_evaluation_edition_triggers_an_automation():
    with patch(
        "envergo.evaluations.tasks.post_evaluation_to_automation.delay"
    ) as mock_post:
        evaluation = EvaluationFactory()  # no call from creation
        evaluation.application_number = "PC05112321D0001"
        evaluation.save()  # call from edition
        evaluation2 = EvaluationFactory()  # no call from creation
        Evaluation.objects.update(
            application_number="PC05112321D0001"
        )  # call from edition for all the evaluations

    mock_post.assert_has_calls(
        [
            call(evaluation.uid),
            call(evaluation.uid),
            call(evaluation2.uid),
        ]
    )
