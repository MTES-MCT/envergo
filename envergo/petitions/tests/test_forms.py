from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from envergo.moulinette.regulations import HedgeCategory
from envergo.petitions.forms import (
    REFUSAL_DEADLINE_PLACEHOLDER,
    PetitionProjectForm,
    ResumeProcessingForm,
    StateChangeForm,
    two_months_from_today,
)
from envergo.petitions.tests.factories import FILE_TEST_NOK_PATH, FILE_TEST_PATH

pytestmark = pytest.mark.django_db


class TestResumeProcessingFormDueDate:
    """The due date field only makes sense when a deadline can be postponed."""

    def test_due_date_removed_without_original_due_date(self):
        form = ResumeProcessingForm(original_due_date=None)

        assert "due_date" not in form.fields
        assert "info_receipt_date" in form.fields

    def test_due_date_removed_by_default(self):
        """No original due date passed at all"""
        form = ResumeProcessingForm()

        assert "due_date" not in form.fields

    def test_due_date_kept_with_original_due_date(self):
        form = ResumeProcessingForm(original_due_date=date(2026, 1, 1))

        assert "due_date" in form.fields

    def test_due_date_initial_is_two_months_from_today(self):
        form = ResumeProcessingForm(original_due_date=date(2026, 1, 1))

        expected = (timezone.now().date() + relativedelta(months=2)).isoformat()
        assert form.fields["due_date"].initial() == expected

    def test_valid_without_due_date_when_no_original_due_date(self):
        form = ResumeProcessingForm(
            data={"info_receipt_date": "2026-01-15"}, original_due_date=None
        )

        assert form.is_valid(), form.errors

    def test_due_date_required_when_original_due_date_is_set(self):
        form = ResumeProcessingForm(
            data={"info_receipt_date": "2026-01-15"},
            original_due_date=date(2026, 1, 1),
        )

        assert not form.is_valid()
        assert "due_date" in form.errors


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


def make_state_change_form(
    data=None,
    files=None,
    previous_stage="preparing_decision",
    single_procedure=False,
    can_switch_to_authorization=False,
):
    """Build a StateChangeForm the way the procedure view does."""
    initial = {"stage": previous_stage, "decision": "unset"}
    return StateChangeForm(
        data=data,
        files=files,
        initial=initial,
        single_procedure=single_procedure,
        can_switch_to_authorization=can_switch_to_authorization,
    )


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


def test_to_be_processed_is_not_reachable_from_another_stage():
    """Once instruction has started, the "to_be_processed" stage cannot be selected again."""
    form = make_state_change_form(
        {
            "stage": "to_be_processed",
            "decision": "dropped",
            "status_date": "10/09/2025",
        },
        previous_stage="instruction_d",
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0].startswith(
        "L'étape « À instruire » n’est plus disponible"
    )


def test_to_be_processed_self_transition_is_allowed():
    """Staying on "to_be_processed" (no actual transition) must not trigger the rule."""
    form = make_state_change_form(
        {"stage": "to_be_processed", "decision": "unset", "status_date": "10/09/2025"},
        previous_stage="to_be_processed",
    )

    assert form.is_valid(), form.errors


def test_closed_to_to_be_processed_is_forbidden():
    form = make_state_change_form(
        {
            "stage": "to_be_processed",
            "decision": "dropped",
            "status_date": "10/09/2025",
        },
        previous_stage="closed",
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0].startswith(
        "L'étape « À instruire » n’est plus disponible"
    )


def test_to_be_processed_to_closed_is_forbidden():
    form = make_state_change_form(
        {"stage": "closed", "decision": "dropped", "status_date": "10/09/2025"},
        previous_stage="to_be_processed",
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0] == (
        "Pour clore le dossier, il faut passer par une étape intermédiaire "
        "(autre que « À instruire »)."
    )


def test_closed_to_closed_is_forbidden():
    form = make_state_change_form(
        {"stage": "closed", "decision": "dropped", "status_date": "10/09/2025"},
        previous_stage="closed",
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0] == (
        "Pour pouvoir changer la décision d'un dossier clos il faut d'abord le "
        "repasser à une étape d'instruction."
    )


def test_entering_authorization_without_switch_is_forbidden():
    form = make_state_change_form(
        {"stage": "instruction_a", "decision": "unset", "status_date": "10/09/2025"},
        previous_stage="preparing_decision",
    )

    assert not form.is_valid()
    assert form.errors["stage"][0].startswith(
        "L'étape « Instruction autorisation » n'est accessible que"
    )


def test_staying_in_authorization_is_allowed():
    form = make_state_change_form(
        {"stage": "instruction_a", "decision": "unset", "status_date": "10/09/2025"},
        previous_stage="instruction_a",
    )

    assert form.is_valid(), form.errors


def make_switch_form(**overrides):
    """A switch from declaration to authorisation, valid unless overridden."""
    data = {
        "stage": "instruction_a",
        "decision": "unset",
        "status_date": date.today().isoformat(),
        "due_date": two_months_from_today().isoformat(),
        "applicant_message": f"Votre projet relève de l'autorisation.\n{REFUSAL_DEADLINE_PLACEHOLDER}",
        **overrides,
    }
    return make_state_change_form(
        data, previous_stage="instruction_d", can_switch_to_authorization=True
    )


def test_valid_switch_writes_the_due_date_into_the_message():
    """The applicant reads the very deadline saved in the due date field."""
    form = make_switch_form(due_date="2099-09-21")

    assert form.is_valid(), form.errors
    assert form.is_authorization_switch
    assert form.cleaned_data["due_date"] == date(2099, 9, 21)
    assert form.cleaned_data["applicant_message"] == (
        "Votre projet relève de l'autorisation.\n"
        "Compte-tenu des avis qui doivent être recueillis, "
        "cette décision interviendra au plus tard le 21 septembre 2099."
    )


def test_switch_accepts_a_placeholder_line_with_stray_spaces():
    """Browsers submit textarea lines with CRLF endings."""
    message = f"Motif.\r\n  {REFUSAL_DEADLINE_PLACEHOLDER} \r\nFin."
    form = make_switch_form(applicant_message=message)

    assert form.is_valid(), form.errors
    assert "au plus tard le" in form.cleaned_data["applicant_message"]


@pytest.mark.parametrize(
    "message",
    [
        "Votre projet relève de l'autorisation.",
        f"Motif. {REFUSAL_DEADLINE_PLACEHOLDER}",
        REFUSAL_DEADLINE_PLACEHOLDER.replace("DATE LIMITE", "Date limite"),
        f"{REFUSAL_DEADLINE_PLACEHOLDER}\n{REFUSAL_DEADLINE_PLACEHOLDER}",
    ],
    ids=["deleted", "not alone on its line", "edited", "duplicated"],
)
def test_switch_message_needs_the_placeholder_line_once_and_intact(message):
    """Only an intact line guarantees the message states the saved deadline."""
    form = make_switch_form(applicant_message=message)

    assert not form.is_valid()
    assert form.has_error(
        "applicant_message", code="altered_refusal_deadline_placeholder"
    )
    assert REFUSAL_DEADLINE_PLACEHOLDER in form.errors["applicant_message"][0]


def test_switch_requires_a_due_date():
    """The due date is the deadline after which silence means refusal."""
    form = make_switch_form(due_date="")

    assert not form.is_valid()
    assert form.has_error("due_date", code="missing_due_date")


def test_switch_due_date_is_at_least_two_months_away():
    """One day before today + 2 months is already too soon."""
    day_too_soon = two_months_from_today() - timedelta(days=1)
    form = make_switch_form(due_date=day_too_soon.isoformat())

    assert not form.is_valid()
    assert form.errors["due_date"] == [
        "Le délai indicatif d'instruction ne peut pas être inférieur à 2 mois."
    ]


def test_switch_with_an_unparsable_due_date_reports_only_the_format_error():
    """A date that fails to parse is not also reported as missing."""
    form = make_switch_form(due_date="pas une date")

    assert not form.is_valid()
    assert not form.has_error("due_date", code="missing_due_date")
    assert form.has_error("due_date", code="invalid")


def test_switch_requires_a_message():
    """Every switch notifies the applicant."""
    form = make_switch_form(applicant_message="")

    assert not form.is_valid()
    assert form.has_error("applicant_message", code="missing_applicant_message")


def test_switch_message_must_not_keep_a_placeholder():
    """The instructor must write the reason for the switch."""
    form = make_switch_form(
        applicant_message="[À COMPLÉTER : motif de la bascule en autorisation]"
    )

    assert not form.is_valid()
    assert form.errors["applicant_message"] == [
        "Complétez le motif de la bascule en autorisation"
    ]


def test_staying_in_authorization_ignores_the_message():
    """Only entering authorisation notifies the applicant."""
    form = make_state_change_form(
        {
            "stage": "instruction_a",
            "decision": "unset",
            "status_date": date.today().isoformat(),
            "applicant_message": "message fantôme",
        },
        previous_stage="instruction_a",
    )

    assert form.is_valid(), form.errors
    assert not form.is_authorization_switch
    assert form.cleaned_data["applicant_message"] == ""


def test_to_be_processed_choice_is_removed_for_single_procedure_projects():
    form = make_state_change_form(
        {
            "stage": "to_be_processed",
            "decision": "dropped",
            "status_date": "10/09/2025",
        },
        previous_stage="to_be_processed",
        single_procedure=True,
    )

    assert not any(
        choice[0] == "to_be_processed" for choice in form.fields["stage"].choices
    )


def test_to_be_processed_choice_is_kept_for_non_single_procedure_projects():
    form = make_state_change_form(
        {
            "stage": "to_be_processed",
            "decision": "dropped",
            "status_date": "10/09/2025",
        },
        previous_stage="to_be_processed",
        single_procedure=False,
    )

    assert any(
        choice[0] == "to_be_processed" for choice in form.fields["stage"].choices
    )


def test_posting_to_be_processed_is_rejected_for_single_procedure_projects():
    """Since the choice is removed entirely, the error comes from the field's
    own choice validation rather than the custom "forbidden_transition" rule."""
    form = make_state_change_form(
        {
            "stage": "to_be_processed",
            "decision": "dropped",
            "status_date": "10/09/2025",
        },
        previous_stage="instruction_d",
        single_procedure=True,
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert "choix valide" in form.errors["stage"][0]


def test_closing_dropped_requires_message_only():
    form = make_state_change_form(
        closing_data("dropped", simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {"applicant_message"}

    form = make_state_change_form(closing_data("dropped", simulation_check=""))
    assert form.is_valid(), form.errors


def test_closing_tacit_agreement_requires_simulation_check_and_message():
    form = make_state_change_form(
        closing_data("tacit_agreement", simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {"simulation_check", "applicant_message"}

    form = make_state_change_form(closing_data("tacit_agreement"))
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("decision", ["express_agreement", "opposition"])
def test_closing_with_order_requires_all_fields(decision):
    form = make_state_change_form(
        closing_data(decision, simulation_check="", applicant_message="")
    )
    assert not form.is_valid()
    assert set(form.errors) == {
        "simulation_check",
        "prefectural_order",
        "applicant_message",
    }

    form = make_state_change_form(
        closing_data(decision), files={"prefectural_order": make_attachment()}
    )
    assert form.is_valid(), form.errors


def test_closing_simulation_check_error_message():
    form = make_state_change_form(closing_data("tacit_agreement", simulation_check=""))
    assert not form.is_valid()
    assert form.errors["simulation_check"] == [
        "Pour garantir la qualité des données transmises à l'observatoire de la haie, "
        "la cohérence entre le dossier et le document de décision doit être vérifiée."
    ]


def test_closing_without_decision_is_invalid():
    form = make_state_change_form(closing_data("unset"))
    assert not form.is_valid()
    assert "decision" in form.errors


def test_closing_forces_hidden_fields():
    """When closing, the comment and date fields are forced server-side."""
    form = make_state_change_form(
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
    form = make_state_change_form(
        closing_data("tacit_agreement"),
        files={"prefectural_order": make_attachment()},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["prefectural_order"] is None


def test_closing_fields_are_ignored_when_not_closing():
    form = make_state_change_form(
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
    form = make_state_change_form(
        closing_data("opposition"), files={"prefectural_order": attachment}
    )
    assert not form.is_valid()
    assert "prefectural_order" in form.errors
