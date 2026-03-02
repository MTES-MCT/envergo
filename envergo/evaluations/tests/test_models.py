from unittest.mock import call, patch
from urllib.parse import urlencode

import pytest
from django.contrib.gis.geos import MultiPolygon

from envergo.evaluations.models import Evaluation, EvaluationSnapshot
from envergo.evaluations.tests.factories import EvaluationFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map  # noqa
from envergo.geodata.tests.factories import MapFactory, ZoneFactory, france_polygon
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


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


@pytest.mark.django_db(transaction=True)
class TestEvaluationSnapshot:
    """Tests for EvaluationSnapshot model and automatic creation."""

    @pytest.mark.parametrize("footprint", [1200])
    def test_create_for_evaluation(self, moulinette_url):
        """EvaluationSnapshot.create_for_evaluation creates a snapshot with correct data."""
        evaluation = EvaluationFactory(moulinette_url=moulinette_url)

        # Clear any snapshots created during evaluation creation
        EvaluationSnapshot.objects.filter(evaluation=evaluation).delete()

        snapshot = EvaluationSnapshot.create_for_evaluation(evaluation=evaluation)

        assert snapshot.evaluation == evaluation
        assert snapshot.moulinette_url == evaluation.moulinette_url
        assert isinstance(snapshot.payload, dict)
        # The payload should contain moulinette summary data
        assert "lat" in snapshot.payload
        assert "lng" in snapshot.payload
        assert "department" in snapshot.payload

    @pytest.mark.parametrize("footprint", [1200])
    def test_snapshot_created_on_evaluation_publication(self, moulinette_url, user):
        """An EvaluationSnapshot is created when an Evaluation version is published."""
        initial_count = EvaluationSnapshot.objects.count()

        evaluation = EvaluationFactory(moulinette_url=moulinette_url)
        evaluation.create_version(user, "initial")

        # A snapshot should have been created
        assert EvaluationSnapshot.objects.count() == initial_count + 1
        snapshot = EvaluationSnapshot.objects.filter(evaluation=evaluation).first()
        assert snapshot is not None
        assert snapshot.moulinette_url == evaluation.moulinette_url

    @pytest.mark.parametrize("footprint", [1200])
    def test_no_snapshot_when_no_version(self, moulinette_url):
        """No EvaluationSnapshot is created when no version have been published."""
        evaluation = EvaluationFactory(moulinette_url=moulinette_url)

        # No new snapshot should have been created
        assert EvaluationSnapshot.objects.filter(evaluation=evaluation).count() == 0
