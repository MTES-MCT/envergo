import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse

from envergo.evaluations.admin import EvaluationAdmin
from envergo.evaluations.models import (
    Evaluation,
    RegulatoryNoticeLog,
    generate_reference,
)
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory
from envergo.moulinette.tests.factories import CriterionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def form_data():
    return {
        "moulinette_url": "http://envergo.local?created_surface=200&final_surface=800&lng=-1.30933&lat=47.11971",  # noqa
        "reference": generate_reference(),
        "user_type": "instructor",
        "address": "Sunny side of the street",
        "contact_emails": ["test@example.org"],
    }


def test_create_eval_from_request(client, admin_user, eval_request):
    qs = Evaluation.objects.all()
    assert qs.count() == 0

    client.force_login(admin_user)
    url = reverse("admin:evaluations_request_changelist")
    data = {"action": "make_evaluation", "_selected_action": eval_request.id}

    res = client.post(url, data=data, follow=True)
    assert "Le nouvel avis réglementaire a été créé" in res.content.decode()
    assert qs.count() == 1

    eval = qs[0]
    assert eval.request == eval_request
    assert eval.reference == eval_request.reference
    assert eval.address == eval_request.address
    assert eval.contact_emails == eval_request.contact_emails


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
        "Cette demande est déjà associée avec un avis réglementaire existant"
        in res.content.decode()
    )
    assert qs.count() == 1


def test_form_validation_without_moulinette_url(form_data):
    """Test field constraints when moulinette url is not set."""

    del form_data["moulinette_url"]

    admin = EvaluationAdmin(model=Evaluation, admin_site=AdminSite())
    EvaluationForm = admin.get_form(request=None, obj=None)
    form = EvaluationForm(form_data)

    assert not form.is_valid()
    assert "created_surface" in form.errors
    assert "contact_md" in form.errors


def test_form_validation_contact_field_with_moulinette_url(form_data):
    """Test field constraints when moulinette url is set."""

    admin = EvaluationAdmin(model=Evaluation, admin_site=AdminSite())
    EvaluationForm = admin.get_form(request=None, obj=None)
    form = EvaluationForm(form_data)

    assert form.is_valid()


def test_regulatory_notice_sending(admin_client, evaluation, mailoutbox):
    # Make sure the "loi sur l'eau" result will be set
    CriterionFactory()

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    res = admin_client.post(url)
    assert len(mailoutbox) == 1
    assert RegulatoryNoticeLog.objects.count() == 1

    log = RegulatoryNoticeLog.objects.first()
    assert log.evaluation == evaluation
