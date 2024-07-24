from unittest.mock import patch

import pytest
from django.contrib.sites.models import Site

from envergo.users.models import User
from envergo.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def admin_user() -> User:
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture(autouse=True)
def mock_get_current_site():
    # Create a mock site
    mock_site = Site()
    mock_site.domain = "www.example.com"
    mock_site.name = "example"

    # Use patch to replace get_current_site with your mock
    with patch(
        "django.contrib.sites.shortcuts.get_current_site", return_value=mock_site
    ):
        yield
