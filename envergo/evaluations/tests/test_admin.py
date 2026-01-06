import pytest
from django.urls import reverse

from envergo.evaluations.models import (
    Evaluation,
    RegulatoryNoticeLog,
    generate_reference,
)
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory
from envergo.geodata.conftest import france_map  # noqa
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def form_data():
    return {
        "moulinette_url": "http://envergo.local?created_surface=200&final_surface=800&lng=-1.646947&lat=47.696706",  # noqa
        "reference": generate_reference(),
        "user_type": "instructor",
        "address": "Sunny side of the street",
        "urbanism_department_emails": ["test@example.org"],
        "project_owner_emails": ["sponsor@example.org"],
    }


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def loisurleau_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="loi_sur_leau")
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneHumide",
            activation_map=france_map,
        ),
    ]
    return criteria


@pytest.fixture()
def admin_client(admin_client):
    admin_client.force_template_rendering = (
        True  # enforce template rendering, and context processors triggering
    )
    return admin_client


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
    assert eval.urbanism_department_emails == eval_request.urbanism_department_emails


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


def test_evaluation_email_sending(admin_client, evaluation, mailoutbox):
    # Make sure the "loi sur l'eau" result will be set
    ConfigAmenagementFactory()

    # Force the moulinette result
    moulinette = evaluation.get_moulinette()
    assert moulinette.is_valid(), moulinette.form_errors()
    evaluation._moulinette.result = "soumis"

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    email = evaluation.get_evaluation_email()
    to = email.get_recipients()
    cc = email.get_cc_recipients()
    bcc = email.get_bcc_recipients()
    assert to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert cc == ["instructor@example.org"]
    assert bcc == []

    data = {"to": to, "cc": cc, "bcc": bcc}

    res = admin_client.post(url, data=data)
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.to == to
    assert mail.cc == cc
    assert mail.bcc == bcc

    assert RegulatoryNoticeLog.objects.count() == 1
    log = RegulatoryNoticeLog.objects.first()
    assert log.evaluation == evaluation


def test_evaluation_email_without_to_recipient_should_use_cc_instead(
    admin_client, evaluation, mailoutbox
):
    # Make sure the "loi sur l'eau" result will be set
    ConfigAmenagementFactory()

    # Force the moulinette result
    evaluation.get_moulinette()
    evaluation._moulinette.result = "soumis"

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    email = evaluation.get_evaluation_email()
    cc = email.get_cc_recipients()
    bcc = email.get_bcc_recipients()
    assert cc == ["instructor@example.org"]
    assert bcc == []

    data = {"to": [], "cc": cc, "bcc": bcc}

    admin_client.post(url, data=data)
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.to == cc
    assert mail.cc == []
    assert mail.bcc == bcc

    assert RegulatoryNoticeLog.objects.count() == 1
    log = RegulatoryNoticeLog.objects.first()
    assert log.evaluation == evaluation


def test_evaluation_email_throttling(admin_client, evaluation, mailoutbox):
    # Make sure the "loi sur l'eau" result will be set
    CriterionFactory()
    ConfigAmenagementFactory()

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    email = evaluation.get_evaluation_email()
    to = email.get_recipients()
    cc = email.get_cc_recipients()
    bcc = email.get_bcc_recipients()
    data = {"to": to, "cc": cc, "bcc": bcc}

    res = admin_client.post(url, data=data)
    assert len(mailoutbox) == 1
    assert RegulatoryNoticeLog.objects.count() == 1

    res = admin_client.post(url, data=data, follow=True)
    assert len(mailoutbox) == 1
    assert RegulatoryNoticeLog.objects.count() == 1
    assert (
        "Il s&#x27;est écoulé moins de 10 secondes depuis le dernier envoi"
        in res.content.decode()
    )


def test_evaluation_email_recipient_overriding(admin_client, evaluation, mailoutbox):
    # Make sure the "loi sur l'eau" result will be set
    CriterionFactory()
    ConfigAmenagementFactory()

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    to = ["sponsor1@example.org"]
    cc = []
    bcc = []
    data = {"to": to, "cc": cc, "bcc": bcc}
    res = admin_client.post(url, data=data)
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.to == to
    assert mail.cc == cc
    assert mail.bcc == bcc


def test_evaluation_email_with_empty_recipients(admin_client, evaluation, mailoutbox):
    # Make sure the "loi sur l'eau" result will be set
    CriterionFactory()
    ConfigAmenagementFactory()

    url = reverse("admin:evaluations_evaluation_email_avis", args=[evaluation.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    assert len(mailoutbox) == 0
    assert RegulatoryNoticeLog.objects.count() == 0

    to = []
    cc = []
    bcc = []
    data = {"to": to, "cc": cc, "bcc": bcc}
    res = admin_client.post(url, data=data, follow=True)
    assert len(mailoutbox) == 0
    assert "Vous devez spécifier au moins un destinataire" in res.content.decode()


def test_display_published_version_message(evaluation, admin_client, admin_user):
    # GIVEN an evaluation with a version not published
    url = reverse("admin:evaluations_evaluation_change", args=[evaluation.pk])
    # WHEN i display the evaluation admin page
    res = admin_client.get(url)
    content = res.content.decode()
    # THEN I see a message indicating the version is not published
    assert "❗️ Publier" in content
    assert "La dernière version n&#x27;est pas publiée." in content

    # GIVEN the version is published
    version = evaluation.versions.first()
    version.published = True
    version.save()
    # WHEN I display the evaluation admin page
    res = admin_client.get(url)
    content = res.content.decode()
    # THEN The button is indicating that the version is published
    assert "✅ Publié" in content

    # GIVEN an outdated version
    evaluation.is_icpe = True
    evaluation.save()

    # WHEN I display the evaluation admin page
    res = admin_client.get(url)
    content = res.content.decode()
    # THEN There is a message indicating that the version is outdated
    assert "❗️ Publier" in content
    assert "La dernière version enregistrée de cet avis" in content
    assert "a pas encore été publiée. Dernière publication :" in content

    # GIVEN an updated version
    version.published = False
    version.save()
    version = evaluation.create_version(admin_user, "v1.0")
    version.published = True
    version.save()
    res = admin_client.get(url)
    content = res.content.decode()
    assert "✅ Publié" in content

    # WHEN I edit the evaluation but that do not impact the AR itself
    evaluation.send_eval_to_project_owner = not evaluation.send_eval_to_project_owner
    evaluation.save()
    res = admin_client.get(url)
    content = res.content.decode()
    # THEN There is no message indicating that the version is outdated
    assert "✅ Publié" in content
