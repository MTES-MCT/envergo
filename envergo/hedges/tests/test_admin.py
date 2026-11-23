import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from envergo.hedges.admin import SpeciesHabitatFileAdminForm

pytestmark = pytest.mark.django_db


def file_errors(upload):
    form = SpeciesHabitatFileAdminForm(data={}, files={"file": upload})
    form.is_valid()
    return form.errors.get("file")


def test_species_habitat_file_accepts_csv():
    csv = b"cd_ref,habitat\n1234,haie\n5678,bosquet\n"
    assert not file_errors(SimpleUploadedFile("species.csv", csv))


def test_species_habitat_file_rejects_other_extension():
    assert file_errors(SimpleUploadedFile("species.pdf", b"%PDF-1.4\n%%EOF"))


def test_species_habitat_file_rejects_content_not_matching_extension():
    assert file_errors(SimpleUploadedFile("species.csv", b"%PDF-1.4\n%%EOF"))
