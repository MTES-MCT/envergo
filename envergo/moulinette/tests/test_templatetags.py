from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.db.backends.postgresql.psycopg_any import DateRange
from django.template import Context

from envergo.evaluations.models import RESULTS, TAG_STYLES_BY_RESULT, TagStyleEnum
from envergo.evaluations.templatetags.evaluations import result_tag
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.templatetags.moulinette import (
    display_validity_range,
    humanize_motif,
    show_regulation_body,
)


def test_display_choice():
    result = humanize_motif("amelioration_culture")
    assert "Modification de parcelle agricole" in result


class TestDisplayValidityRange:

    def test_none_returns_empty_string(self):
        assert display_validity_range(None) == ""

    def test_both_bounds(self):
        r = DateRange(date(2025, 1, 1), date(2025, 12, 31), "[)")
        result = display_validity_range(r)
        # Upper is exclusive in DB, displayed as inclusive (minus 1 day)
        assert result == "du 01/01/2025 au 30/12/2025"

    def test_upper_bound_only(self):
        r = DateRange(None, date(2026, 6, 1), "[)")
        result = display_validity_range(r)
        assert result == "jusqu'au 31/05/2026"

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


class TestResultTag:

    def test_auto_resolves_style_when_none(self):
        """Calling result_tag without style auto-resolves from TAG_STYLES_BY_RESULT."""
        html = result_tag(RESULTS.soumis)
        expected_style = TAG_STYLES_BY_RESULT[RESULTS.soumis]
        assert f"probability-{expected_style.value}" in html

    def test_explicit_style_overrides_default(self):
        """Passing an explicit style uses it instead of the default."""
        html = result_tag(RESULTS.soumis, result_tag_style=TagStyleEnum.Green)
        assert f"probability-{TagStyleEnum.Green.value}" in html
        default_style = TAG_STYLES_BY_RESULT[RESULTS.soumis]
        assert f"probability-{default_style.value}" not in html

    def test_result_label_in_output(self):
        """The result label appears in the rendered tag."""
        html = result_tag(RESULTS.non_concerne)
        assert RESULTS[RESULTS.non_concerne] in html


class TestShowRegulationBody:
    """A regulation may provide a template per hedge category, or a single one."""

    def build_context(self, regulation, category, db_templates=None):
        moulinette = SimpleNamespace(templates=db_templates or {})
        return Context(
            {
                "moulinette": moulinette,
                "regulation": regulation,
                "category": category,
            }
        )

    def build_regulation(self, slug, result, category):
        return SimpleNamespace(
            slug=slug, result=result, results_by_category={category: result}
        )

    def test_category_template_is_preferred(self):
        """Sites protégés has one "soumis" template per category."""
        category = HedgeCategory.ru
        regulation = self.build_regulation("sites_proteges_haie", "soumis", category)

        content = show_regulation_body(
            self.build_context(regulation, category), regulation, category
        )

        # The "régime unique" wording, not the "autorisation préalable" one.
        assert "C’est le guichet unique qui instruit le projet." in content
        assert "L’autorisation de travaux doit être déposée en mairie." not in content

    def test_other_category_template(self):
        category = HedgeCategory.l350_3
        regulation = self.build_regulation("sites_proteges_haie", "soumis", category)

        content = show_regulation_body(
            self.build_context(regulation, category), regulation, category
        )

        assert "L’autorisation de travaux doit être déposée en mairie." in content

    def test_fallback_on_category_agnostic_template(self):
        """Regulations without per category templates keep their single one."""
        category = HedgeCategory.ru
        regulation = self.build_regulation("loi_sur_leau_haie", "soumis", category)

        content = show_regulation_body(
            self.build_context(regulation, category), regulation, category
        )

        assert content != ""

    def test_missing_template_renders_nothing(self):
        category = HedgeCategory.ru
        regulation = self.build_regulation("sites_proteges_haie", "interdit", category)

        content = show_regulation_body(
            self.build_context(regulation, category), regulation, category
        )

        assert content == ""

    def test_database_override_wins_over_file_system(self):
        """A department override targets the category agnostic key too."""
        category = HedgeCategory.ru
        regulation = self.build_regulation("sites_proteges_haie", "soumis", category)
        db_templates = {
            "sites_proteges_haie/result_soumis.html": SimpleNamespace(
                content="<p>Texte du département</p>"
            )
        }

        content = show_regulation_body(
            self.build_context(regulation, category, db_templates), regulation, category
        )

        assert content == "<p>Texte du département</p>"
