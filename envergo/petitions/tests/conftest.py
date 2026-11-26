import shutil

import pytest
from django.contrib.staticfiles import finders
from django.test import override_settings


@pytest.fixture
def collected_fonts(tmp_path):
    """A static folder holding the DSFR fonts, as `collectstatic` leaves it."""
    fonts_folder = "@gouvfr/dsfr/dist/fonts"
    shutil.copytree(finders.find(fonts_folder), tmp_path / fonts_folder)
    with override_settings(STATIC_ROOT=str(tmp_path)):
        yield
