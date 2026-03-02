from unittest.mock import MagicMock, Mock
from urllib.parse import urlencode

import pytest

from envergo.evaluations.models import USER_TYPES
from envergo.evaluations.tests.factories import EvaluationFactory
from envergo.moulinette.regulations import RequiredAction, Stake
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    PerimeterFactory,
    RegulationFactory,
)


@pytest.fixture(autouse=True)
def override_settings(settings):
    settings.FROM_EMAIL["amenagement"]["evaluations"] = "envergo-test@example.org"


@pytest.fixture(autouse=True)
def moulinette_config(france_map, france_zh, loire_atlantique_department):  # noqa
    ConfigAmenagementFactory(
        department=loire_atlantique_department,
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )
    regulation = RegulationFactory()
    perimeter = PerimeterFactory(
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
            regulation=regulation,
            activation_map=france_map,
            evaluator=path,
            perimeter=perimeter,
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


def fake_moulinette(
    url, lse, n2000, evalenv, sage, sage_results_by_perimeter=None, **eval_kwargs
):
    """Create a moulinette with custom regulation results."""

    eval_params = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": url,
        "send_eval_to_project_owner": True,
    }
    eval_params.update(eval_kwargs)

    eval = EvaluationFactory(**eval_params)
    moulinette = eval.get_moulinette()

    # We create mocks based on a real regulation, so it's easier to fake results
    regulation = RegulationFactory()
    sage_perimeter = Mock(contact_email="sage@example.com")
    moulinette.regulations = [
        Mock(
            wraps=regulation,
            result=lse,
            slug="loi_sur_leau",
            do_not_call_in_templates=True,
        ),
        Mock(
            wraps=regulation,
            result=n2000,
            slug="natura2000",
            do_not_call_in_templates=True,
        ),
        Mock(
            wraps=regulation,
            result=evalenv,
            slug="eval_env",
            do_not_call_in_templates=True,
        ),
        Mock(
            wraps=regulation,
            result=sage,
            perimeters=Mock(all=MagicMock(return_value=[sage_perimeter])),
            slug="sage",
            do_not_call_in_templates=True,
            results_by_perimeter=(
                sage_results_by_perimeter
                if sage_results_by_perimeter
                else {sage_perimeter: sage}
            ),
        ),
    ]

    # We monkeypatch this method, so that the `eval.get_evaluation_email` uses the
    # same moulinette object that we mocked here.
    eval.get_moulinette = lambda: moulinette

    return eval, moulinette


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_dont_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is not checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": False,
        "project_owner_emails": [],
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" in body
    assert "Acceptez-vous que nous lui transmettions cet avis ?" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_self_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is not checked
    - the "project owner" emails is filled
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": False,
        "project_owner_emails": ["owner@example.org"],
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body
    assert "Acceptez-vous que nous lui transmettions cet avis ?" in body


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_transmit_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]
    assert email.bcc == ["ddtm_email_test@example.org"]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_instructor_transmit_n2000_evalenv_soumis(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - the "send to sponsor" checkbox is checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "soumis",
        "systematique",
        "soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]

    assert email.bcc == [
        "ddtm_email_test@example.org",
        "ddtm_n2000@example.org",
        "dreal_evalenv@example.org",
        "sage@example.com",
    ]

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [800])
def test_instructor_transmit_action_requise(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "action requise"
    - the "send to sponsor" checkbox is checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "action_requise",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
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
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "non_soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_petitioner(rf, moulinette_url):
    eval_kwargs = {
        "user_type": USER_TYPES.petitioner,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": False,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.from_email == "envergo-test@example.org"
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body


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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    body = email.alternatives[0][0]
    assert "Le projet est soumis à la Loi sur l'eau" in body
    assert "Le projet est soumis à Natura 2000" not in body
    assert "Le projet est soumis à examen au cas par cas" not in body
    assert "Le projet est soumis à évaluation environnementale" not in body


@pytest.mark.parametrize("footprint", [1200])
def test_lse_soumis_ou_pac_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "soumis_ou_pac", "non_soumis", "non_soumis", "non_soumis"
    )
    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    body = email.alternatives[0][0]
    assert "Le projet est soumis à la Loi sur l'eau" in body
    assert "Le projet est soumis à Natura 2000" not in body
    assert "Le projet est soumis à examen au cas par cas" not in body
    assert "Le projet est soumis à évaluation environnementale" not in body
    assert "ddtm_email_test@example.org" in email.bcc


@pytest.mark.parametrize("footprint", [1200])
def test_n2000_soumis_content(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "non_soumis", "soumis", "non_soumis", "non_soumis"
    )
    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" not in body
    assert "une action du porteur de projet est requise" in body
    assert (
        "Pour s'assurer que le projet n'est pas soumis à la <b>Loi sur l'eau</b>"
        in body
    )
    assert (
        "Pour s'assurer que le projet n'est pas soumis à <b>Natura 2000</b>" not in body
    )
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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" not in body
    assert "une action du porteur de projet est requise" in body
    assert (
        "Pour s'assurer que le projet n'est pas soumis à la <b>Loi sur l'eau</b>"
        not in body
    )
    assert "Pour s'assurer que le projet n'est pas soumis à <b>Natura 2000</b>" in body
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
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    body = email.alternatives[0][0]

    assert "ce projet est susceptible d'être interdit" in body
    assert "Celui-ci doit mener les études pour s'assurer que le projet" in body
    assert (
        "Pour s'assurer que le projet n'est pas soumis à la <b>Loi sur l'eau</b>"
        not in body
    )
    assert (
        "Pour s'assurer que le projet n'est pas soumis à <b>Natura 2000</b>" not in body
    )
    assert "action attendue du porteur" not in body
    assert "action requise interdit" in body


@pytest.mark.parametrize("footprint", [50])
def test_instructor_icpe_send_to_sponsor(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the "icpe" checkbox is checked
    - send eval to sponsor is checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
        "is_icpe": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body
    assert (
        "Le projet semble être une Installation Classée pour la Protection de l’Environnement (ICPE)"
        in body
    )
    assert (
        "nous n’avons pas envoyé cet avis directement au porteur, car Envergo ne se prononce pas encore"
        in body
    )


@pytest.mark.parametrize("footprint", [50])
def test_instructor_icpe_dont_send_to_sponsor(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the "icpe" checkbox is checked
    - send eval to sponsor is not checked
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": False,
        "is_icpe": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.to == ["instructor@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body
    assert (
        "Le projet semble être une Installation Classée pour la Protection de l’Environnement (ICPE)"
        in body
    )
    assert (
        "nous n’avons pas envoyé cet avis directement au porteur, car Envergo ne se prononce pas encore"
        not in body
    )


@pytest.mark.parametrize("footprint", [1200])
def test_petitioner_icpe(rf, moulinette_url):
    eval_kwargs = {
        "user_type": USER_TYPES.petitioner,
        "is_icpe": True,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": False,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "non_soumis",
        "non_soumis",
        "non_soumis",
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)

    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == []
    assert email.bcc == []

    body = email.body
    assert "À transmettre au porteur" not in body
    assert (
        "Le projet semble être une Installation Classée pour la Protection de l’Environnement (ICPE)"
        in body
    )
    assert (
        "nous n’avons pas envoyé cet avis directement au porteur, car Envergo ne se prononce pas encore"
        not in body
    )


@pytest.mark.parametrize("footprint", [1200])
def test_n2000_ein_out_of_n2000_site_no_bcc(rf, moulinette_url):
    eval, moulinette = fake_moulinette(
        moulinette_url, "soumis", "soumis", "non_soumis", "non_soumis"
    )
    moulinette.regulations[1].configure_mock(ein_out_of_n2000_site=lambda: True)

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert "ddtm_n2000@example.org" not in email.bcc


@pytest.mark.parametrize("footprint", [1200])
def test_multiple_sage(rf, moulinette_url):
    """Test email when evalreq is:
    - created by an instructor
    - the eval result is "soumis"
    - there is multiple Sage perimeter impacted with different results
    """
    eval_kwargs = {
        "user_type": USER_TYPES.instructor,
        "moulinette_url": moulinette_url,
        "send_eval_to_project_owner": True,
    }
    eval, moulinette = fake_moulinette(
        moulinette_url,
        "soumis",
        "soumis",
        "systematique",
        "soumis",
        sage_results_by_perimeter={
            Mock(contact_email="sage_interdit@example.com"): "interdit",
            Mock(contact_email="sage_action_requise@example.com"): "action_requise",
            Mock(contact_email="sage_non_disponible@example.com"): "non_disponible",
        },
        **eval_kwargs,
    )

    req = rf.get("/")
    eval_email = eval.get_evaluation_email()
    email = eval_email.get_email(req)
    assert email.to == ["sponsor1@example.org", "sponsor2@example.org"]
    assert email.cc == ["instructor@example.org"]

    assert email.bcc == [
        "ddtm_email_test@example.org",
        "ddtm_n2000@example.org",
        "dreal_evalenv@example.org",
        "sage_action_requise@example.com",
        "sage_interdit@example.com",
    ]

    body = email.body
    assert "À transmettre au porteur" not in body
