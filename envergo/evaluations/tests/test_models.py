from unittest.mock import call, patch
from urllib.parse import urlencode

import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.evaluations.models import Evaluation
from envergo.evaluations.tests.factories import EvaluationFactory
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    PerimeterFactory,
    RegulationFactory,
)


@pytest.fixture(autouse=True)
def moulinette_config(france_map, loire_atlantique_department):  # noqa
    ConfigAmenagementFactory(
        department=loire_atlantique_department,
        is_activated=True,
        lse_contact_ddtm="Contact de la DDTM du 44",
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )
    regulation = RegulationFactory(regulation="loi_sur_leau")
    PerimeterFactory(
        regulations=[regulation],
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
        # Mouais coordinates
        "lat": 47.696706,
        "lng": -1.646947,
        "created_surface": footprint,
        "final_surface": footprint,
    }
    url = urlencode(params)
    return f"https://envergo.beta.gouv.fr?{url}"


@pytest.mark.parametrize("footprint", [1200])
def test_call_to_action_action(moulinette_url):
    evaluation = EvaluationFactory(moulinette_url=moulinette_url)
    moulinette = evaluation.get_moulinette()

    assert not evaluation.is_icpe

    assert moulinette.result == "non_soumis"
    assert not evaluation.is_eligible_to_self_declaration()

    moulinette.regulations[0].criteria.first()._evaluator._result = "action_requise"
    assert evaluation.is_eligible_to_self_declaration()

    moulinette.regulations[0].criteria.first()._evaluator._result = "soumis"
    assert evaluation.is_eligible_to_self_declaration()

    moulinette.regulations[0].criteria.first()._evaluator._result = "interdit"
    assert evaluation.is_eligible_to_self_declaration()

    evaluation.is_icpe = True
    evaluation.save()
    assert not evaluation.is_eligible_to_self_declaration()


def test_evaluation_edition_triggers_an_automation():
    with patch("django.db.transaction.on_commit", new=lambda fn: fn()):
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


@pytest.mark.parametrize("footprint", [5000])
def test_render_context(moulinette_url):
    # GIVEN an evaluation that is "soumis" to Loi sur l'Eau due to presence of wetland
    wetland = MapFactory(map_type="zone_humide", zones=None, data_type="certain")
    ZoneFactory(map=wetland, geometry=MultiPolygon([france_polygon]))

    evaluation = EvaluationFactory(moulinette_url=moulinette_url)
    # WHEN rendering the content
    content = evaluation.render_content()

    # THEN some info from configuration are present in the content
    assert "Contact de la DDTM du 44" in content
