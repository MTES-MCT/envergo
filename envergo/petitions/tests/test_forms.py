import pytest

from envergo.petitions.forms import ProcedureForm


def make_form(
    previous_stage, stage, decision="dropped", single_procedure=False, **extra_data
):
    data = {
        "stage": stage,
        "decision": decision,
        "status_date": "10/09/2025",
        **extra_data,
    }
    return ProcedureForm(
        data=data,
        initial={"stage": previous_stage},
        single_procedure=single_procedure,
    )


@pytest.mark.django_db
def test_to_be_processed_is_not_reachable_from_another_stage():
    """Once instruction has started, the "to_be_processed" stage cannot be selected again."""
    form = make_form(previous_stage="instruction_d", stage="to_be_processed")

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0].startswith(
        "L'étape « À instruire » n’est plus disponible"
    )


@pytest.mark.django_db
def test_to_be_processed_self_transition_is_allowed():
    """Staying on "to_be_processed" (no actual transition) must not trigger the rule."""
    form = make_form(
        previous_stage="to_be_processed", stage="to_be_processed", decision="unset"
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_closed_to_to_be_processed_is_forbidden():
    form = make_form(previous_stage="closed", stage="to_be_processed")

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0].startswith(
        "L'étape « À instruire » n’est plus disponible"
    )


@pytest.mark.django_db
def test_to_be_processed_to_closed_is_forbidden():
    form = make_form(previous_stage="to_be_processed", stage="closed")

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0] == (
        "Pour clore le dossier, il faut passer par une étape intermédiaire "
        "(autre que « À instruire »)."
    )


@pytest.mark.django_db
def test_closed_to_closed_is_forbidden():
    form = make_form(previous_stage="closed", stage="closed")

    assert not form.is_valid()
    assert "stage" in form.errors
    assert form.errors["stage"][0] == (
        "Pour pouvoir changer la décision d'un dossier clos il faut d'abord le "
        "repasser à une étape d'instruction."
    )


@pytest.mark.django_db
def test_to_be_processed_choice_is_removed_for_single_procedure_projects():
    form = make_form(
        previous_stage="to_be_processed", stage="to_be_processed", single_procedure=True
    )

    assert not any(
        choice[0] == "to_be_processed" for choice in form.fields["stage"].choices
    )


@pytest.mark.django_db
def test_to_be_processed_choice_is_kept_for_non_single_procedure_projects():
    form = make_form(
        previous_stage="to_be_processed",
        stage="to_be_processed",
        single_procedure=False,
    )

    assert any(
        choice[0] == "to_be_processed" for choice in form.fields["stage"].choices
    )


@pytest.mark.django_db
def test_posting_to_be_processed_is_rejected_for_single_procedure_projects():
    """Since the choice is removed entirely, the error comes from the field's
    own choice validation rather than the custom "forbidden_transition" rule."""
    form = make_form(
        previous_stage="instruction_d", stage="to_be_processed", single_procedure=True
    )

    assert not form.is_valid()
    assert "stage" in form.errors
    assert "choix valide" in form.errors["stage"][0]
