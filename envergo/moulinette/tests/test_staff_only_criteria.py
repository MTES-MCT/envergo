import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import COORDS_BIZOU, make_amenagement_data
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

BASE_PARAMS = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


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

    def test_non_staff_cannot_see_icpe_result(self, client):
        params = (
            f"{BASE_PARAMS}"
            "&evalenv_icpe-activate=on"
            "&evalenv_icpe-icpe_projet=creation"
            "&evalenv_icpe-icpe_regime=enregistrement"
        )
        url = f"{reverse('moulinette_result')}?{params}"
        res = client.get(url)

        assert res.status_code == 200
        assert "installation classée (icpe)" not in res.content.decode().lower()

    def test_staff_can_see_icpe_result(self, staff_client):
        params = (
            f"{BASE_PARAMS}"
            "&evalenv_icpe-activate=on"
            "&evalenv_icpe-icpe_projet=creation"
            "&evalenv_icpe-icpe_regime=enregistrement"
        )
        url = f"{reverse('moulinette_result')}?{params}"
        res = staff_client.get(url)

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/result.html")
        assert "installation classée (icpe)" in res.content.decode().lower()

    def test_staff_haie_only_cannot_see_icpe_form(self, client):
        user = UserFactory(is_staff=True, access_amenagement=False, access_haie=True)
        client.force_login(user)
        url = reverse("moulinette_form")
        res = client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" not in res.content.decode()

    def test_superuser_non_staff_can_see_icpe_form(self, client):
        user = UserFactory(is_superuser=True, is_staff=False)
        client.force_login(user)
        url = reverse("moulinette_form")
        res = client.get(url)

        assert res.status_code == 200
        assert "Installation classée (ICPE)" in res.content.decode()


class TestStaffOnlyFiltering:
    def _make_moulinette(self):
        data = make_amenagement_data(
            lat=COORDS_BIZOU[0],
            lng=COORDS_BIZOU[1],
            created_surface=500,
            final_surface=500,
        )
        return MoulinetteAmenagement(data)

    def test_optional_form_classes_excludes_staff_only_by_default(self):
        moulinette = self._make_moulinette()
        form_classes = moulinette.optional_form_classes()
        class_names = [fc.__name__ for fc in form_classes]
        assert "ICPEForm" not in class_names

    def test_optional_form_classes_includes_staff_only_when_requested(self):
        moulinette = self._make_moulinette()
        form_classes = moulinette.optional_form_classes(
            exclude_staff_only_criterion=False
        )
        class_names = [fc.__name__ for fc in form_classes]
        assert "ICPEForm" in class_names


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
