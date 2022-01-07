import pytest

from envergo.evaluations.models import RESULTS
from envergo.evaluations.tests.factories import CriterionFactory, EvaluationFactory

pytestmark = pytest.mark.django_db


def test_evaluation_status_soumis():

    evaluation = EvaluationFactory(result=None, criterions=[])
    CriterionFactory(
        evaluation=evaluation, criterion="rainwater_runoff", result=RESULTS.soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="flood_zone", result=RESULTS.non_soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="wetland", result=RESULTS.non_soumis
    )

    assert evaluation.compute_result() == RESULTS.soumis


def test_evaluation_status_soumis_2():

    evaluation = EvaluationFactory(result=None, criterions=[])
    CriterionFactory(
        evaluation=evaluation, criterion="rainwater_runoff", result=RESULTS.soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="flood_zone", result=RESULTS.soumis
    )
    CriterionFactory(evaluation=evaluation, criterion="wetland", result=RESULTS.soumis)

    assert evaluation.compute_result() == RESULTS.soumis


def test_evaluation_status_soumis_3():

    evaluation = EvaluationFactory(result=None, criterions=[])
    CriterionFactory(
        evaluation=evaluation, criterion="rainwater_runoff", result=RESULTS.soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="flood_zone", result=RESULTS.action_requise
    )
    CriterionFactory(
        evaluation=evaluation, criterion="wetland", result=RESULTS.action_requise
    )

    assert evaluation.compute_result() == RESULTS.soumis


def test_evaluation_status_non_soumis():

    evaluation = EvaluationFactory(result=None, criterions=[])
    CriterionFactory(
        evaluation=evaluation, criterion="rainwater_runoff", result=RESULTS.non_soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="flood_zone", result=RESULTS.non_soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="wetland", result=RESULTS.non_soumis
    )

    assert evaluation.compute_result() == RESULTS.non_soumis


def test_evaluation_status_action_requise():

    evaluation = EvaluationFactory(result=None, criterions=[])
    CriterionFactory(
        evaluation=evaluation,
        criterion="rainwater_runoff",
        result=RESULTS.action_requise,
    )
    CriterionFactory(
        evaluation=evaluation, criterion="flood_zone", result=RESULTS.non_soumis
    )
    CriterionFactory(
        evaluation=evaluation, criterion="wetland", result=RESULTS.non_soumis
    )

    assert evaluation.compute_result() == RESULTS.action_requise
