import pytest
from django.urls import reverse

from envergo.evaluations.models import Evaluation
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory

pytestmark = pytest.mark.django_db


def test_create_eval_from_request(client, admin_user, eval_request):
    qs = Evaluation.objects.all()
    assert qs.count() == 0

    client.force_login(admin_user)
    url = reverse("admin:evaluations_request_changelist")
    data = {"action": "make_evaluation", "_selected_action": eval_request.id}

    res = client.post(url, data=data, follow=True)
    assert "La nouvelle évaluation a été créée" in res.content.decode()
    assert qs.count() == 1

    eval = qs[0]
    assert eval.request == eval_request
    assert eval.reference == eval_request.reference
    assert eval.address == eval_request.address
    assert eval.created_surface == eval_request.created_surface
    assert eval.existing_surface == eval_request.existing_surface
    assert eval.contact_email == eval_request.contact_email


def test_create_eval_requires_a_single_request(client, admin_user):
    qs = Evaluation.objects.all()
    assert qs.count() == 0

    client.force_login(admin_user)
    url = reverse("admin:evaluations_request_changelist")
    data = {
        "action": "make_evaluation",
        "_selected_action": [RequestFactory().id, RequestFactory().id],
    }

    res = client.post(url, data=data, follow=True)
    assert "Merci de sélectionner une et une seule demande" in res.content.decode()
    assert qs.count() == 0


def test_create_eval_fails_when_it_already_exists(client, admin_user, eval_request):
    EvaluationFactory(request=eval_request)
    qs = Evaluation.objects.all()
    assert qs.count() == 1

    client.force_login(admin_user)
    url = reverse("admin:evaluations_request_changelist")
    data = {"action": "make_evaluation", "_selected_action": eval_request.id}

    res = client.post(url, data=data, follow=True)
    assert (
        "Cette demande est déjà associée avec une évaluation existante"
        in res.content.decode()
    )
    assert qs.count() == 1
