import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.regulations.evalenv import ICPEForm, OptionalFormMixin
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import COORDS_BIZOU, make_amenagement_data
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

BASE_PARAMS = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"

ICPE_RESULT_PARAMS = (
    f"{BASE_PARAMS}"
    "&evalenv_icpe-activate=on"
    "&evalenv_icpe-icpe_projet=creation"
    "&evalenv_icpe-icpe_regime=enregistrement"
)


@pytest.fixture(autouse=True)
def icpe_criterion(france_map):
    config = ConfigAmenagementFactory(is_activated=True)  # noqa
    regulation = RegulationFactory(regulation="eval_env")
    return CriterionFactory(
        title="Cas par cas pour une installation classée (ICPE)",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.ICPE",
        activation_map=france_map,
        is_optional=True,
        is_staff_only=True,
    )


class TestICPEStaffOnlyVisibility:
    def test_non_staff_cannot_see_icpe_form(self, client):
        url = reverse("moulinette_form")
        res = client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" not in res.content.decode()

    def test_staff_can_see_icpe_form(self, staff_client):
        url = reverse("moulinette_form")
        res = staff_client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" in res.content.decode()

    def test_non_staff_can_see_icpe_result(self, client):
        url = f"{reverse('moulinette_result')}?{ICPE_RESULT_PARAMS}"
        res = client.get(url)

        assert res.status_code == 200
        assert "installation classée (icpe)" in res.content.decode().lower()

    def test_staff_can_see_icpe_result(self, staff_client):
        url = f"{reverse('moulinette_result')}?{ICPE_RESULT_PARAMS}"
        res = staff_client.get(url)

        assert res.status_code == 200
        assertTemplateUsed(res, "amenagement/moulinette/result.html")
        assert "installation classée (icpe)" in res.content.decode().lower()

    def test_staff_haie_only_can_see_icpe_form(self, client):
        user = UserFactory(is_staff=True, access_amenagement=False, access_haie=True)
        client.force_login(user)
        url = reverse("moulinette_form")
        res = client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" in res.content.decode()

    def test_superuser_non_staff_can_see_icpe_form(self, client):
        user = UserFactory(is_superuser=True, is_staff=False)
        client.force_login(user)
        url = reverse("moulinette_form")
        res = client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" in res.content.decode()


class TestStaffOnlyFormAttribute:
    def test_optional_form_mixin_defaults_to_not_staff_only(self):
        assert OptionalFormMixin.is_staff_only is False

    def test_icpe_form_is_staff_only(self):
        assert ICPEForm.is_staff_only is True


class TestStaffOnlyFiltering:
    def make_moulinette(self, **extra):
        data = make_amenagement_data(
            lat=COORDS_BIZOU[0],
            lng=COORDS_BIZOU[1],
            created_surface=500,
            final_surface=500,
            **extra,
        )
        return MoulinetteAmenagement(data)

    def test_optional_form_classes_includes_staff_only(self):
        moulinette = self.make_moulinette()
        form_classes = moulinette.optional_form_classes()
        class_names = [fc.__name__ for fc in form_classes]
        assert "ICPEForm" in class_names

    def test_optional_forms_property_includes_staff_only(self):
        """The cached property always includes staff-only forms."""
        moulinette = self.make_moulinette()
        form_types = [type(f) for f in moulinette.optional_forms]
        assert ICPEForm in form_types

    def test_get_all_forms_includes_staff_only(self):
        """get_all_forms() includes staff-only optional forms."""
        moulinette = self.make_moulinette()
        form_types = [type(f) for f in moulinette.get_all_forms()]
        assert ICPEForm in form_types

    def test_optional_fields_includes_staff_only(self):
        """optional_fields includes fields from staff-only forms."""
        moulinette = self.make_moulinette()
        assert any(
            key.startswith("evalenv_icpe-") for key in moulinette.optional_fields.keys()
        )


class TestCriterionStaffOnlyValidation:
    def test_staff_only_requires_is_optional(self, france_map):
        regulation = RegulationFactory(regulation="eval_env")
        criterion = CriterionFactory(
            title="Test",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.ICPE",
            activation_map=france_map,
            is_optional=False,
            is_staff_only=True,
        )
        with pytest.raises(ValidationError) as exc_info:
            criterion.full_clean()
        assert "is_optional" in exc_info.value.message_dict

    def test_staff_only_with_optional_is_valid(self, france_map):
        regulation = RegulationFactory(regulation="eval_env")
        criterion = CriterionFactory(
            title="Test",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.ICPE",
            activation_map=france_map,
            is_optional=True,
            is_staff_only=True,
        )
        try:
            criterion.full_clean()
        except ValidationError:
            pytest.fail("full_clean() raised ValidationError unexpectedly")


class TestStaffOnlyViewContext:
    """The view injects a filtered optional_forms list into the template context."""

    def test_form_page_excludes_staff_only_for_anonymous(self, client):
        url = reverse("moulinette_form")
        res = client.get(url)

        optional_forms = res.context["optional_forms"]
        form_types = [type(f) for f in optional_forms]
        assert ICPEForm not in form_types

    def test_form_page_includes_staff_only_for_staff(self, staff_client):
        url = reverse("moulinette_form")
        res = staff_client.get(url)

        optional_forms = res.context["optional_forms"]
        form_types = [type(f) for f in optional_forms]
        assert ICPEForm in form_types

    def test_result_page_includes_staff_only_for_non_staff(self, client):
        """The result page processes all submitted forms, even for non-staff."""
        url = f"{reverse('moulinette_result')}?{ICPE_RESULT_PARAMS}"
        res = client.get(url)

        assert res.status_code == 200
        content = res.content.decode()
        assert "Oui, il crée une nouvelle ICPE" in content


class TestStaffOnlySummaryRendering:
    """The _additional_specifications template shows activated staff-only fields."""

    def test_icpe_fields_in_result_summary_for_non_staff(self, client):
        """ICPE field values appear in the result summary even for non-staff users."""
        url = f"{reverse('moulinette_result')}?{ICPE_RESULT_PARAMS}"
        res = client.get(url)

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/_additional_specifications.html")
        content = res.content.decode()
        assert "ICPE-E" in content or "enregistrement" in content.lower()
