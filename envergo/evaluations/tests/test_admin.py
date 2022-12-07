import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse

from envergo.evaluations.admin import EvaluationAdmin
from envergo.evaluations.models import Evaluation, generate_reference
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def form_data():
    return {
        "reference": generate_reference(),
        "address": "Sunny side of the street",
        "created_surface": 20,
        "existing_surface": 42,
        "contact_email": "test@example.org",
        "contact_md": "Léotard Tiflette",
    }


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


def test_form_validation_without_moulinette_url(rf, form_data):
    """The `result` is not required since it's computed."""

    admin = EvaluationAdmin(model=Evaluation, admin_site=AdminSite())
    request = rf.get("/admin/evaluations/evaluation/add/")
    EvaluationForm = admin.get_form(request=None, obj=None)
    form = EvaluationForm(form_data)
    assert form.is_valid()


def test_form_validation_with_moulinette_url(rf, form_data):
    """When a moulinette url is set, the `result` field must be set."""

    admin = EvaluationAdmin(model=Evaluation, admin_site=AdminSite())
    request = rf.get("/admin/evaluations/evaluation/add/")
    EvaluationForm = admin.get_form(request=None, obj=None)

    form_data[
        "moulinette_url"
    ] = "http://envergo.local:8000/simulateur/resultat/?created_surface=2000&existing_surface=20&lng=-1.30933&lat=47.11971"  # noqa
    form = EvaluationForm(form_data)
    assert not form.is_valid()
    assert "result" in form.errors

    form_data["result"] = "soumis"
    form = EvaluationForm(form_data)
    assert form.is_valid()
