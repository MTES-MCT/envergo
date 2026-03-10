"""Shared fixtures for evaluations tests.

Centralizes common fixture imports and autouse fixtures that were
previously duplicated across individual test files.
"""

import pytest

# Re-export geodata fixtures so evaluations tests can use them without
# explicit imports from envergo.geodata.conftest.
from envergo.geodata.conftest import (  # noqa: F401
    bizous_town_center,
    france_map,
    france_zh,
    loire_atlantique_department,
    loire_atlantique_map,
)
from envergo.moulinette.tests.factories import ConfigAmenagementFactory


@pytest.fixture(autouse=True)
def autouse_site(db, site):
    """Ensure DB access and a Site object for all evaluations tests.

    Requesting ``db`` grants database access (equivalent to the
    ``django_db`` mark), so individual test files no longer need
    ``pytestmark = pytest.mark.django_db``.
    """
    pass


@pytest.fixture()
def moulinette_config(loire_atlantique_department):  # noqa: F811
    """ConfigAmenagement with standard email fields.

    Not autouse — tests that need more complex setups (regulations,
    criteria) define their own local fixture that builds on top.
    """
    ConfigAmenagementFactory(
        department=loire_atlantique_department,
        is_activated=True,
        ddtm_water_police_email="ddtm_email_test@example.org",
        ddtm_n2000_email="ddtm_n2000@example.org",
        dreal_eval_env_email="dreal_evalenv@example.org",
    )
