from datetime import date

import pytest
from django.db.backends.postgresql.psycopg_any import DateRange

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_INSIDE,
    make_moulinette_haie_data,
    make_hedge,
)


@pytest.fixture(autouse=True)
def n2000_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(regulation="natura2000_haie", has_perimeters=True)

    perimeter = PerimeterFactory(
        name="N2000 Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous 2025",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            validity_range=DateRange(date(2025, 1, 1), date(2026, 1, 1), "[)"),
            evaluator_settings={"result": "soumis"},
        ),
        CriterionFactory(
            title="Natura 2000 Haie > Haie Bizous 2026",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.natura2000_haie.Natura2000Haie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
            validity_range=DateRange(date(2026, 1, 1), None, "[)"),
            evaluator_settings={"result": "soumis"},
        ),
    ]
    return criteria


def test_moulinette_validity_date_on_criteria():
    """Test criteria evaluated according to date in moulinette data"""
    DCConfigHaieFactory()
    data = make_moulinette_haie_data(
        hedge_data=[make_hedge(coords=COORDS_BIZOUS_INSIDE)],
        reimplantation="replantation",
    )

    # GIVEN moulinette data without date
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(data)
    # THEN only 2026 N2000 criteria is used
    assert "2026" in moulinette.get_criteria().get().title

    # GIVEN moulinette data with date in 2025
    data["data"]["date"] = "2025-03-13"
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(data)
    # THEN only 2025 N2000 criteria is used
    assert "2025" in moulinette.get_criteria().get().title

    # GIVEN moulinette data with date in 2026
    data["data"]["date"] = "2026-03-13"
    # WHEN moulinette data are evaluated
    moulinette = MoulinetteHaie(data)
    # THEN only 2026 N2000 criteria is used
    assert "2026" in moulinette.get_criteria().get().title
