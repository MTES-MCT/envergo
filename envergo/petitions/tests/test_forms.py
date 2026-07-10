from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from envergo.moulinette.regulations import HedgeCategory
from envergo.petitions.forms import PetitionProjectForm, ProcedureForm
from envergo.petitions.tests.factories import FILE_TEST_NOK_PATH, FILE_TEST_PATH

pytestmark = pytest.mark.django_db


class TestPetitionProjectFormCleanCategory:

    def test_valid_category_ru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "ru",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.ru

    def test_valid_category_hru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "hru",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.hru

    def test_valid_category_l350_3(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "l350_3",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.l350_3

    def test_invalid_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "invalid_value",
            }
        )
        assert not form.is_valid()
        assert "_category" in form.errors

    def test_empty_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "",
            }
        )
        assert not form.is_valid()
        assert "_category" in form.errors


def make_procedure_form(data=None, files=None, previous_stage="preparing_decision"):
    """Build a ProcedureForm the way the procedure view does."""
    initial = {"stage": previous_stage, "decision": "unset"}
    return ProcedureForm(data=data, files=files, initial=initial)


def make_attachment():
    return SimpleUploadedFile(FILE_TEST_PATH.name, FILE_TEST_PATH.read_bytes())


def closing_data(decision, **overrides):
    data = {
        "stage": "closed",
        "decision": decision,
        "simulation_check": "on",
        "applicant_message": "Votre dossier a fait l'objet d'une décision.",
    }
    data.update(overrides)
    return data


def test_closing_dropped_requires_message_only():
    form = make_procedure_form(
        closing_data("dropped", simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {"applicant_message"}

    form = make_procedure_form(closing_data("dropped", simulation_check=""))
    assert form.is_valid(), form.errors


def test_closing_tacit_agreement_requires_simulation_check_and_message():
    form = make_procedure_form(
        closing_data("tacit_agreement", simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {"simulation_check", "applicant_message"}

    form = make_procedure_form(closing_data("tacit_agreement"))
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("decision", ["express_agreement", "opposition"])
def test_closing_with_order_requires_all_fields(decision):
    form = make_procedure_form(
        closing_data(decision, simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {
        "simulation_check",
        "prefectural_order",
        "applicant_message",
    }

    form = make_procedure_form(
        closing_data(decision), files={"prefectural_order": make_attachment()}
    )
    assert form.is_valid(), form.errors


def test_closing_simulation_check_error_message():
    form = make_procedure_form(closing_data("tacit_agreement", simulation_check=""))
    assert not form.is_valid()
    assert form.errors["simulation_check"] == [
        "Pour garantir la qualité des données transmises à l'observatoire de la haie, "
        "la cohérence entre le dossier et le document de décision doit être vérifiée."
    ]


def test_closing_without_decision_is_invalid():
    form = make_procedure_form(closing_data("unset"))
    assert not form.is_valid()
    assert "decision" in form.errors


def test_closing_forces_hidden_fields():
    """When closing, the comment and date fields are forced server-side."""
    form = make_procedure_form(
        closing_data(
            "tacit_agreement",
            update_comment="commentaire fantôme",
            due_date="2030-01-01",
            status_date="2020-01-01",
        )
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["update_comment"] == ""
    assert form.cleaned_data["due_date"] is None
    assert form.cleaned_data["status_date"] == timezone.localdate()


def test_closing_drops_stray_order_upload():
    """A file upload is ignored for decisions that do not allow one."""
    form = make_procedure_form(
        closing_data("tacit_agreement"),
        files={"prefectural_order": make_attachment()},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["prefectural_order"] is None


def test_closing_fields_are_ignored_when_not_closing():
    form = make_procedure_form(
        {
            "stage": "instruction_d",
            "decision": "unset",
            "status_date": date.today().isoformat(),
            "applicant_message": "message fantôme",
            "simulation_check": "on",
        },
        files={"prefectural_order": make_attachment()},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["simulation_check"] is False
    assert form.cleaned_data["prefectural_order"] is None
    assert form.cleaned_data["applicant_message"] == ""


def test_closing_order_file_type_is_validated():
    attachment = SimpleUploadedFile(
        FILE_TEST_NOK_PATH.name, FILE_TEST_NOK_PATH.read_bytes()
    )
    form = make_procedure_form(
        closing_data("opposition"), files={"prefectural_order": attachment}
    )
    assert not form.is_valid()
    assert "prefectural_order" in form.errors
