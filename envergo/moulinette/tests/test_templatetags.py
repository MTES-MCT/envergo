from datetime import date
from unittest.mock import patch

from django.db.backends.postgresql.psycopg_any import DateRange

from envergo.moulinette.templatetags.moulinette import (
    display_validity_range,
    humanize_motif,
)


def test_display_choice():
    result = humanize_motif("amelioration_culture")
    assert "Amélioration des conditions d’exploitation agricole" in result


class TestDisplayValidityRange:

    def test_none_returns_empty_string(self):
        assert display_validity_range(None) == ""

    def test_both_bounds(self):
        r = DateRange(date(2025, 1, 1), date(2025, 12, 31), "[)")
        result = display_validity_range(r)
        assert result == "du 01/01/2025 au 31/12/2025"

    def test_upper_bound_only(self):
        r = DateRange(None, date(2026, 6, 1), "[)")
        result = display_validity_range(r)
        assert result == "jusqu'au 01/06/2026"

    @patch("envergo.moulinette.templatetags.moulinette.date")
    def test_lower_bound_only_in_past(self, mock_date):
        mock_date.today.return_value = date(2026, 2, 16)
        r = DateRange(date(2025, 1, 1), None, "[)")
        result = display_validity_range(r)
        assert result == "depuis le 01/01/2025"

    @patch("envergo.moulinette.templatetags.moulinette.date")
    def test_lower_bound_only_today(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 1)
        r = DateRange(date(2025, 1, 1), None, "[)")
        result = display_validity_range(r)
        assert result == "depuis le 01/01/2025"

    @patch("envergo.moulinette.templatetags.moulinette.date")
    def test_lower_bound_only_in_future(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 1)
        r = DateRange(date(2026, 6, 1), None, "[)")
        result = display_validity_range(r)
        assert result == "à partir du 01/06/2026"
