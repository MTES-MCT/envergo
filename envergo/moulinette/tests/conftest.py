"""Shared fixtures for moulinette tests.

Centralizes common fixture imports and autouse fixtures that were
previously duplicated across individual test files.
"""

import pytest

# Re-export geodata fixtures so moulinette tests can use them without
# explicit imports from envergo.geodata.conftest. Pytest discovers these
# automatically through the conftest.py fixture resolution chain.
from envergo.geodata.conftest import (  # noqa: F401
    bizous_town_center,
    france_map,
    herault_map,
    loire_atlantique_department,
    loire_atlantique_map,
)


@pytest.fixture(autouse=True)
def autouse_site(db, site):
    """Ensure DB access and a Site object for all moulinette tests.

    Requesting ``db`` grants database access (equivalent to the
    ``django_db`` mark), so individual test files no longer need
    ``pytestmark = pytest.mark.django_db``.

    The ``site`` fixture (from envergo/conftest.py) creates a Site via
    SiteFactory — needed because moulinette views and models rely on
    the Django sites framework.
    """
    pass
