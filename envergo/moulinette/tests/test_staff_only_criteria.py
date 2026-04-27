import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.tests.factories import (
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

BASE_PARAMS = "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"


@pytest.fixture
def staff_client():
    user = UserFactory(is_staff=True)
    client = Client()
    client.force_login(user)
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
        assert "installation classée (ICPE)" not in res.content.decode()

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
        assert "installation classée (ICPE)" in res.content.decode()


class TestICPEResults:
    def _get_result(self, staff_client, icpe_projet, icpe_regime):
        params = (
            f"{BASE_PARAMS}"
            f"&evalenv_icpe-activate=on"
            f"&evalenv_icpe-icpe_projet={icpe_projet}"
            f"&evalenv_icpe-icpe_regime={icpe_regime}"
        )
        url = f"{reverse('moulinette_result')}?{params}"
        return staff_client.get(url)

    def test_creation_enregistrement_is_cas_par_cas(self, staff_client):
        res = self._get_result(staff_client, "creation", "enregistrement")
        content = res.content.decode()

        assert res.status_code == 200
        assert "cas par cas" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_cas_par_cas.html")

    def test_modif_avec_pac_enregistrement_is_cas_par_cas(self, staff_client):
        res = self._get_result(staff_client, "modif_avec_pac", "enregistrement")
        content = res.content.decode()

        assert res.status_code == 200
        assert "cas par cas" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_cas_par_cas.html")

    def test_creation_declaration_is_non_soumis(self, staff_client):
        res = self._get_result(staff_client, "creation", "declaration")
        content = res.content.decode()

        assert res.status_code == 200
        assert "non soumis" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_non_soumis_declaration.html")

    def test_modif_sans_pac_enregistrement_is_non_soumis(self, staff_client):
        res = self._get_result(staff_client, "modif_sans_pac", "enregistrement")
        content = res.content.decode()

        assert res.status_code == 200
        assert "non soumis" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_non_soumis_sans_pac.html")

    def test_aucun_aucun_is_non_soumis(self, staff_client):
        res = self._get_result(staff_client, "aucun", "aucun")
        content = res.content.decode()

        assert res.status_code == 200
        assert "non soumis" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_non_soumis_pas_icpe.html")

    def test_creation_inconnu_is_a_verifier(self, staff_client):
        res = self._get_result(staff_client, "creation", "inconnu")
        content = res.content.decode()

        assert res.status_code == 200
        assert "à vérifier" in content.lower()
        assertTemplateUsed(res, "moulinette/eval_env/icpe_a_verifier.html")


class TestICPEFormValidation:
    def test_aucun_projet_with_regime_is_invalid(self, staff_client):
        """aucun projet + enregistrement regime = contradictory, redirects to form."""
        res = self._get_result(staff_client, "aucun", "enregistrement")

        assert res.status_code == 302
        assert "/formulaire/" in res["Location"]

    def test_projet_with_aucun_regime_is_invalid(self, staff_client):
        """creation projet + aucun regime = contradictory, redirects to form."""
        res = self._get_result(staff_client, "creation", "aucun")

        assert res.status_code == 302
        assert "/formulaire/" in res["Location"]

    def test_coherent_answers_are_valid(self, staff_client):
        """creation + enregistrement = valid, shows result page."""
        res = self._get_result(staff_client, "creation", "enregistrement")

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/result.html")

    def _get_result(self, staff_client, icpe_projet, icpe_regime):
        params = (
            f"{BASE_PARAMS}"
            f"&evalenv_icpe-activate=on"
            f"&evalenv_icpe-icpe_projet={icpe_projet}"
            f"&evalenv_icpe-icpe_regime={icpe_regime}"
        )
        url = f"{reverse('moulinette_result')}?{params}"
        return staff_client.get(url)


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
