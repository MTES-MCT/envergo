import pytest

from envergo.moulinette.forms.fields import (
    DisplayIntegerField,
    extract_display_function,
)
from envergo.utils.fields import EnrichedChoices


class TestDisplayIntegerField:
    """Tests for DisplayIntegerField whitespace stripping."""

    def test_strips_regular_spaces(self):
        field = DisplayIntegerField()
        assert field.clean("8 000") == 8000

    def test_strips_multiple_spaces(self):
        field = DisplayIntegerField()
        assert field.clean("1 000 000") == 1000000

    def test_strips_non_breaking_spaces(self):
        field = DisplayIntegerField()
        # \u00a0 is non-breaking space, \u202f is narrow non-breaking space
        assert field.clean("8\u00a0000") == 8000
        assert field.clean("8\u202f000") == 8000

    def test_strips_tabs(self):
        field = DisplayIntegerField()
        assert field.clean("8\t000") == 8000

    def test_handles_normal_integer(self):
        field = DisplayIntegerField()
        assert field.clean("8000") == 8000

    def test_handles_integer_value(self):
        field = DisplayIntegerField()
        assert field.clean(8000) == 8000

    def test_handles_empty_value(self):
        field = DisplayIntegerField(required=False)
        assert field.clean("") is None


class EnrichedTestedChoices(EnrichedChoices):
    first_entry = {
        "label": "Le libellé de la première entrée",
        "help_text": "Une petite note en-dessous",
    }
    second_entry = "Du texte sans info en plus"
    third_entry = {
        "label": "Une troisième entrée",
        "display_label": "Entrée 3",
    }


class TestEnrichedChoices:
    def test_handles_enriched_and_string_values(self):
        choices = EnrichedTestedChoices.choices
        assert len(choices) == 3

        first_choice = choices[0]
        assert first_choice[0] == "first_entry"
        assert first_choice[1].value == "first_entry"
        assert first_choice[1].label == "Le libellé de la première entrée"
        assert first_choice[1].help_text == "Une petite note en-dessous"

        second_choice = choices[1]
        assert second_choice[0] == "second_entry"
        assert second_choice[1].value == "second_entry"
        assert second_choice[1].label == "Du texte sans info en plus"


@pytest.fixture
def classic_display_choices():
    return (
        ("aucune", "Aucune", "Aucune"),
        ("lt_10km", "De 0 (dès le premier mètre) à 10 km", "Moins de 10 km"),
        ("gte_10km", "10 km ou plus", "10 km ou plus"),
    )


class TestDisplayValue:
    def test_extract_display_value_classic_choices(self, classic_display_choices):
        display_function = extract_display_function(classic_display_choices)
        assert display_function("aucune") == "Aucune"
        assert display_function("lt_10km") == "Moins de 10 km"

    def test_extract_display_value_enriched_choices(self):
        display_function = extract_display_function(EnrichedTestedChoices)
        assert display_function("second_entry") == "Du texte sans info en plus"
        assert display_function("third_entry") == "Entrée 3"
