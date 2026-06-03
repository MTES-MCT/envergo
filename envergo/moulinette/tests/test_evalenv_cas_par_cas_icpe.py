"""Tests for the cas_par_cas_icpe macro-result feature.

Verifies that when ICPE is the only criterion triggering cas par cas,
the EvalEnv regulation produces the `cas_par_cas_icpe` macro-result instead
of `cas_par_cas`, with corresponding changes to actions and templates.
"""

from unittest.mock import Mock

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from envergo.moulinette.models import MoulinetteAmenagement
from envergo.moulinette.tests.factories import (
    ActionToTakeFactory,
    ConfigAmenagementFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.moulinette.tests.utils import COORDS_MOUAIS, make_amenagement_data


def mouais_data(created_surface, **extra):
    """Shortcut for Mouais-located amenagement data with common evalenv fields."""
    defaults = {
        "emprise": 20000,
        "zone_u": "oui",
        "surface_plancher_sup_thld": "oui",
        "is_lotissement": "non",
        "terrain_assiette": 150000,
        "operation_amenagement": "non",
    }
    defaults.update(extra)
    return make_amenagement_data(
        lat=COORDS_MOUAIS[0],
        lng=COORDS_MOUAIS[1],
        created_surface=created_surface,
        final_surface=created_surface,
        **defaults,
    )


def mouais_data_with_icpe(created_surface, icpe_projet, icpe_regime, **extra):
    """Shortcut for data that includes ICPE criterion form fields."""
    icpe_fields = {
        "evalenv_icpe-activate": "on",
        "evalenv_icpe-icpe_projet": icpe_projet,
        "evalenv_icpe-icpe_regime": icpe_regime,
    }
    return mouais_data(created_surface, **icpe_fields, **extra)


@pytest.fixture
def evalenv_regulation(france_map):
    """Set up EvalEnv regulation with Emprise + ICPE criteria."""
    ConfigAmenagementFactory(is_activated=True)
    regulation = RegulationFactory(
        regulation="eval_env",
        evaluator="envergo.moulinette.regulations.evalenv.EvalEnvRegulation",
    )
    CriterionFactory(
        title="Emprise",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.Emprise",
        activation_map=france_map,
    )
    CriterionFactory(
        title="Surface Plancher",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.SurfacePlancher",
        activation_map=france_map,
    )
    CriterionFactory(
        title="Terrain d'assiette",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.TerrainAssiette",
        activation_map=france_map,
    )
    CriterionFactory(
        title="ICPE",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.evalenv.ICPE",
        activation_map=france_map,
        is_optional=True,
        is_staff_only=True,
    )
    return regulation


# ---------------------------------------------------------------------------
# Macro-result cascade
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("evalenv_regulation")
class TestCasParCasIcpeMacroResult:
    """When only ICPE triggers cas par cas, the macro-result is cas_par_cas_icpe."""

    def test_icpe_only_cas_par_cas_gives_cas_par_cas_icpe(self):
        """ICPE creation+E = cas_par_cas_icpe, emprise non_soumis -> macro = cas_par_cas_icpe."""
        data = mouais_data_with_icpe(500, "creation", "enregistrement")
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.icpe.result == "cas_par_cas_icpe"
        assert moulinette.eval_env.emprise.result == "non_soumis"
        assert moulinette.eval_env.result == "cas_par_cas_icpe"

    def test_icpe_modif_cas_par_cas_gives_cas_par_cas_icpe(self):
        """ICPE modif_avec_pac+E = cas_par_cas_icpe -> macro = cas_par_cas_icpe."""
        data = mouais_data_with_icpe(500, "modif_avec_pac", "enregistrement")
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.icpe.result == "cas_par_cas_icpe"
        assert moulinette.eval_env.result == "cas_par_cas_icpe"

    def test_icpe_plus_emprise_cas_par_cas_gives_cas_par_cas(self):
        """ICPE cas_par_cas + Emprise cas_par_cas -> macro = cas_par_cas (not icpe)."""
        data = mouais_data_with_icpe(
            10000, "creation", "enregistrement", emprise=10000
        )
        del data["data"]["zone_u"]
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.icpe.result == "cas_par_cas_icpe"
        assert moulinette.eval_env.emprise.result == "cas_par_cas"
        assert moulinette.eval_env.result == "cas_par_cas"

    def test_emprise_cas_par_cas_without_icpe_gives_cas_par_cas(self):
        """Emprise cas_par_cas without ICPE -> macro = cas_par_cas (unchanged behavior)."""
        data = mouais_data(10000, emprise=10000)
        del data["data"]["zone_u"]
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.emprise.result == "cas_par_cas"
        assert moulinette.eval_env.result == "cas_par_cas"

    def test_emprise_systematique_trumps_icpe_cas_par_cas(self):
        """Emprise systematique + ICPE cas_par_cas -> macro = systematique."""
        data = mouais_data_with_icpe(
            40000, "creation", "enregistrement", emprise=40000, zone_u="non"
        )
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.emprise.result == "systematique"
        assert moulinette.eval_env.icpe.result == "cas_par_cas_icpe"
        assert moulinette.eval_env.result == "systematique"

    def test_a_verifier_macro_result_unchanged(self):
        """ICPE a_verifier alone -> macro = a_verifier (no new macro-result needed)."""
        data = mouais_data_with_icpe(500, "creation", "inconnu")
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.icpe.result == "a_verifier"
        assert moulinette.eval_env.result == "a_verifier"


# ---------------------------------------------------------------------------
# Action suppression
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("evalenv_regulation")
class TestCasParCasIcpeActions:
    """depot_cas_par_cas action is suppressed when macro-result is cas_par_cas_icpe."""

    def action_slugs(self, moulinette):
        """Flatten actions_to_take into a set of slugs."""
        slugs = set()
        for actions_list in moulinette.actions_to_take.values():
            for action in actions_list:
                slugs.add(action.slug)
        return slugs

    def test_no_depot_cas_par_cas_when_icpe_only(self):
        """cas_par_cas_icpe -> depot_cas_par_cas and pc_cas_par_cas not in actions."""
        ActionToTakeFactory(slug="depot_cas_par_cas", target="petitioner")
        ActionToTakeFactory(slug="pc_cas_par_cas", target="instructor")
        ActionToTakeFactory(slug="depot_dossier_icpe", target="petitioner")
        ActionToTakeFactory(slug="pc_icpe_e", target="instructor")

        data = mouais_data_with_icpe(500, "creation", "enregistrement")
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.result == "cas_par_cas_icpe"
        slugs = self.action_slugs(moulinette)
        assert "depot_cas_par_cas" not in slugs
        assert "pc_cas_par_cas" not in slugs

    def test_depot_cas_par_cas_present_when_other_criterion(self):
        """cas_par_cas (from Emprise) -> depot_cas_par_cas IS in actions."""
        ActionToTakeFactory(slug="depot_cas_par_cas", target="petitioner")
        ActionToTakeFactory(slug="pc_cas_par_cas", target="instructor")

        data = mouais_data(10000, emprise=10000)
        del data["data"]["zone_u"]
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.result == "cas_par_cas"
        slugs = self.action_slugs(moulinette)
        assert "depot_cas_par_cas" in slugs

    def test_depot_cas_par_cas_present_when_icpe_plus_other(self):
        """cas_par_cas (ICPE + Emprise) -> depot_cas_par_cas IS in actions."""
        ActionToTakeFactory(slug="depot_cas_par_cas", target="petitioner")
        ActionToTakeFactory(slug="pc_cas_par_cas", target="instructor")
        ActionToTakeFactory(slug="depot_dossier_icpe", target="petitioner")

        data = mouais_data_with_icpe(
            10000, "creation", "enregistrement", emprise=10000
        )
        del data["data"]["zone_u"]
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.result == "cas_par_cas"
        slugs = self.action_slugs(moulinette)
        assert "depot_cas_par_cas" in slugs

    def test_no_actions_when_a_verifier(self):
        """a_verifier -> no regulation-level actions added."""
        ActionToTakeFactory(slug="depot_cas_par_cas", target="petitioner")

        data = mouais_data_with_icpe(500, "creation", "inconnu")
        moulinette = MoulinetteAmenagement(data)

        assert moulinette.eval_env.result == "a_verifier"
        regulation_actions = moulinette.eval_env.actions_to_take
        assert regulation_actions.get("to_add", set()) == set()


# ---------------------------------------------------------------------------
# View-level: pink box templates
# ---------------------------------------------------------------------------


ICPE_ONLY_PARAMS = (
    "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
    "&emprise=20000"
    "&zone_u=oui"
    "&surface_plancher_sup_thld=oui"
    "&is_lotissement=non"
    "&terrain_assiette=150000"
    "&operation_amenagement=non"
    "&evalenv_icpe-activate=on"
    "&evalenv_icpe-icpe_projet=creation"
    "&evalenv_icpe-icpe_regime=enregistrement"
)

ICPE_PLUS_EMPRISE_PARAMS = (
    "created_surface=10000&final_surface=10000&lng=-1.54394&lat=47.21381"
    "&emprise=10000"
    "&surface_plancher_sup_thld=oui"
    "&is_lotissement=non"
    "&terrain_assiette=150000"
    "&operation_amenagement=non"
    "&evalenv_icpe-activate=on"
    "&evalenv_icpe-icpe_projet=creation"
    "&evalenv_icpe-icpe_regime=enregistrement"
)


@pytest.mark.usefixtures("evalenv_regulation")
class TestCasParCasIcpeTemplates:
    """Correct pink box template is rendered for each macro-result."""

    def test_cas_par_cas_icpe_renders_dedicated_template(self, staff_client):
        url = reverse("moulinette_result")
        res = staff_client.get(f"{url}?{ICPE_ONLY_PARAMS}")
        content = res.content.decode()

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/eval_env/result_cas_par_cas_icpe.html")
        assert "le dossier ICPE fait office de" in content

    def test_cas_par_cas_with_other_criterion_renders_standard_template(
        self, staff_client
    ):
        url = reverse("moulinette_result")
        res = staff_client.get(f"{url}?{ICPE_PLUS_EMPRISE_PARAMS}")
        content = res.content.decode()

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/eval_env/result_cas_par_cas.html")
        assert "Demande d'examen au cas par cas" in content

    def test_a_verifier_renders_a_verifier_template(self, staff_client):
        url = reverse("moulinette_result")
        params = (
            "created_surface=500&final_surface=500&lng=-1.54394&lat=47.21381"
            "&emprise=20000"
            "&zone_u=oui"
            "&surface_plancher_sup_thld=oui"
            "&is_lotissement=non"
            "&terrain_assiette=150000"
            "&operation_amenagement=non"
            "&evalenv_icpe-activate=on"
            "&evalenv_icpe-icpe_projet=creation"
            "&evalenv_icpe-icpe_regime=inconnu"
        )
        res = staff_client.get(f"{url}?{params}")
        content = res.content.decode()

        assert res.status_code == 200
        assertTemplateUsed(res, "moulinette/eval_env/result_a_verifier.html")
        assert "peut être soumis à examen au cas par cas" in content


# ---------------------------------------------------------------------------
# View-level: depot_dossier_icpe action nota
# ---------------------------------------------------------------------------


class TestDepotDossierIcpeNota:
    """The nota about MRAe cas par cas is shown only when macro-result is cas_par_cas.

    The depot_dossier_icpe.html template is rendered on admin evaluation pages
    only (not on the public moulinette result page), so we test it by rendering
    the template directly with a mock context.
    """

    NOTA_FRAGMENT = "la demande d'examen au cas par cas doit"

    def test_nota_shown_when_cas_par_cas(self):
        """When macro = cas_par_cas, the nota appears."""
        moulinette = Mock()
        moulinette.eval_env.result = "cas_par_cas"
        content = render_to_string(
            "moulinette/actions_to_take/depot_dossier_icpe.html",
            {"moulinette": moulinette, "icpe_regime": "enregistrement"},
        )
        assert self.NOTA_FRAGMENT in content

    def test_nota_hidden_when_cas_par_cas_icpe(self):
        """When macro = cas_par_cas_icpe, the nota does NOT appear."""
        moulinette = Mock()
        moulinette.eval_env.result = "cas_par_cas_icpe"
        content = render_to_string(
            "moulinette/actions_to_take/depot_dossier_icpe.html",
            {"moulinette": moulinette, "icpe_regime": "enregistrement"},
        )
        assert self.NOTA_FRAGMENT not in content
