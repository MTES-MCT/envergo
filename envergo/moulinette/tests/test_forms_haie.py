import pytest

from envergo.moulinette.forms import MoulinetteFormHaie
from envergo.moulinette.tests.factories import RUConfigHaieFactory
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data

pytestmark = pytest.mark.haie


class TestFormSimulation:
    """Tests form simulation hedge to destroy"""

    def test_form_valid(self):
        """Tests form is valid with simple hedges"""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            hedge_data=[make_hedge(type_haie="mixte")],
        )
        form = MoulinetteFormHaie(data["data"])
        assert form.is_valid(), form.errors

    def test_form_errors_no_hedges(self):
        """Tests form errors when no hedges are provide"""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(hedge_data=[])
        data["data"]["haies"] = []
        form = MoulinetteFormHaie(data["data"])
        assert "haies" in form.errors
        assert "Aucune haie n'a été saisie." in form.errors["haies"][0]

    def test_form_errors_parcelle_pac(self):
        """Tests form errors when PAC is selected but no hedge is within PAC area"""
        RUConfigHaieFactory()
        data = make_moulinette_haie_data(
            localisation_pac="oui",
            hedge_data=[make_hedge(type_haie="mixte")],
        )
        form = MoulinetteFormHaie(data["data"])
        assert "haies" in form.errors
        assert (
            "Aucune haie saisie n’a été marquée sur parcelle PAC"
            in form.errors["haies"][0]
        )
