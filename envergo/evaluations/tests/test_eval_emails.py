from unittest.mock import Mock
from urllib.parse import urlencode

import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import EvaluationFactory
from envergo.geodata.conftest import loire_atlantique_department  # noqa
from envergo.geodata.conftest import bizous_town_center, france_map, france_zh  # noqa
from envergo.moulinette.regulations import RequiredAction, Stake
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

    eval = EvaluationFactory(
        user_type=USER_TYPES.instructor,
        moulinette_url=url,
        send_eval_to_sponsor=True,
    )
    moulinette = eval.get_moulinette()

    # We create mocks based on a real regulation, so it's easier to fake results
    regulation = RegulationFactory()
    moulinette.regulations = [
        Mock(
            regulation,
            wraps=regulation,
            result=lse,
            slug="loi_sur_leau",
            do_not_call_in_templates=True,
        ),
        Mock(
            regulation,
            wraps=regulation,
            result=n2000,
            slug="natura_2000",
            do_not_call_in_templates=True,
        ),
        Mock(
            regulation,
            wraps=regulation,
            result=evalenv,
            slug="eval_env",
            do_not_call_in_templates=True,
        ),
        Mock(
            regulation,
            wraps=regulation,
            result=sage,
            slug="sage",
            do_not_call_in_templates=True,
        ),
    ]

    # We monkeypatch this method, so that the `eval.get_evaluation_email` uses the
    # same moulinette object that we mocked here.
    eval.get_moulinette = lambda: moulinette

    return eval, moulinette


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
        _eval, moulinette = fake_moulinette(moulinette_url, *results)
        assert moulinette.result == expected_result


@pytest.mark.parametrize("footprint", [1200])
def test_lse_soumis_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "soumis", "non_soumis", "non_soumis", "non_soumis"
    )
    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]
    assert "Le projet est soumis à la Loi sur l'eau" in body
    assert "Le projet est soumis à Natura 2000" not in body
    assert "Le projet est soumis à examen au cas par cas" not in body
    assert "Le projet est soumis à évaluation environnementale" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_n2000_soumis_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "non_soumis", "soumis", "non_soumis", "non_soumis"
    )
    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "Le projet est soumis à la Loi sur l'eau" not in body
    assert "Le projet est soumis à Natura 2000" in body
    assert "Le projet est soumis à examen au cas par cas" not in body
    assert "Le projet est soumis à évaluation environnementale" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_evalenv_cas_par_cas_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "non_soumis", "non_soumis", "cas_par_cas", "non_soumis"
    )
    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "Le projet est soumis à la Loi sur l'eau" not in body
    assert "Le projet est soumis à Natura 2000" not in body
    assert "Le projet est soumis à examen au cas par cas" in body
    assert "Le projet est soumis à évaluation environnementale" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_evalenv_systematique_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "non_soumis", "non_soumis", "systematique", "non_soumis"
    )
    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "Le projet est soumis à la Loi sur l'eau" not in body
    assert "Le projet est soumis à Natura 2000" not in body
    assert "Le projet est soumis à examen au cas par cas" not in body
    assert "Le projet est soumis à évaluation environnementale" in body


@pytest.mark.parametrize("footprint", [1200])
def test_required_action_lse(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "action_requise", "non_soumis", "non_soumis", "non_soumis"
    )
    moulinette.regulations[0].required_actions_interdit.return_value = []
    moulinette.regulations[0].required_actions_soumis.return_value = [
        RequiredAction(Stake.SOUMIS, "action attendue du porteur")
    ]

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" not in body
    assert "une action du porteur de projet est requise" in body
    assert "Pour s'assurer que le projet n'est pas soumis à la Loi sur l'eau" in body
    assert "Pour s'assurer que le projet n'est pas soumis à Natura 2000" not in body
    assert "action attendue du porteur" in body


@pytest.mark.parametrize("footprint", [1200])
def test_required_action_n2000(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "non_soumis", "action_requise", "non_soumis", "non_soumis"
    )
    moulinette.regulations[1].required_actions_interdit.return_value = []
    moulinette.regulations[1].required_actions_soumis.return_value = [
        RequiredAction(Stake.SOUMIS, "action attendue du porteur")
    ]

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" not in body
    assert "une action du porteur de projet est requise" in body
    assert (
        "Pour s'assurer que le projet n'est pas soumis à la Loi sur l'eau" not in body
    )
    assert "Pour s'assurer que le projet n'est pas soumis à Natura 2000" in body
    assert "action attendue du porteur" in body


@pytest.mark.parametrize("footprint", [1200])
def test_required_action_interdit(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "action_requise", "non_soumis", "non_soumis", "action_requise"
    )
    moulinette.regulations[0].required_actions_interdit.return_value = []
    moulinette.regulations[0].required_actions_soumis.return_value = [
        RequiredAction(Stake.SOUMIS, "action attendue du porteur")
    ]
    moulinette.regulations[3].required_actions_interdit.return_value = [
        RequiredAction(Stake.INTERDIT, "action requise interdit")
    ]
    moulinette.regulations[3].required_actions_soumis.return_value = []

    req = rf.get("/")
    email = eval.get_evaluation_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" in body
    assert "Le porteur doit mener les études pour s'assurer que le projet" in body
    assert (
        "Pour s'assurer que le projet n'est pas soumis à la Loi sur l'eau" not in body
    )
    assert "Pour s'assurer que le projet n'est pas soumis à Natura 2000" not in body
    assert "action attendue du porteur" not in body
    assert "action requise interdit" in body
