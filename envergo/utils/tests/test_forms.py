from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile

from envergo.hedges.admin import SpeciesHabitatFileAdminForm
from envergo.utils.forms import AllowedFileTypesMixin
from envergo.utils.validators import CSV_MIME_TYPES, ZIP_MIME_TYPES


class DummyForm(AllowedFileTypesMixin, forms.Form):
    allowed_file_types = {
        "file": {".csv": CSV_MIME_TYPES, ".zip": ZIP_MIME_TYPES},
        "missing": {".pdf": {"application/pdf"}},
    }

    file = forms.FileField()
    other_file = forms.FileField(required=False)


def test_accept_attribute_is_set_on_listed_fields():
    form = DummyForm()
    assert form.fields["file"].widget.attrs["accept"] == ".csv,.zip"
    assert 'accept=".csv,.zip"' in str(form["file"])


def test_unlisted_fields_are_left_untouched():
    form = DummyForm()
    assert "accept" not in form.fields["other_file"].widget.attrs
    assert form.fields["other_file"].validators == []


def test_validators_do_not_leak_between_form_instances():
    DummyForm()
    form = DummyForm()
    assert len(form.fields["file"].validators) == 1


def test_allowed_file_is_valid():
    file = SimpleUploadedFile("data.csv", b"a,b\n1,2\n", content_type="text/csv")
    form = DummyForm(files={"file": file})
    assert form.is_valid(), form.errors


def test_forbidden_extension_is_rejected():
    file = SimpleUploadedFile("data.txt", b"a,b\n1,2\n", content_type="text/plain")
    form = DummyForm(files={"file": file})
    assert not form.is_valid()
    assert "n'est pas autorisée" in form.errors["file"][0]


def test_content_not_matching_extension_is_rejected():
    file = SimpleUploadedFile("data.zip", b"a,b\n1,2\n", content_type="application/zip")
    form = DummyForm(files={"file": file})
    assert not form.is_valid()
    assert "ne correspond pas" in form.errors["file"][0]


def test_species_habitat_file_admin_form_only_accepts_csv():
    form = SpeciesHabitatFileAdminForm()
    assert form.fields["file"].widget.attrs["accept"] == ".csv"
