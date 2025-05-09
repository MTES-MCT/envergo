from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator


class EspecesProtegees(CriterionEvaluator):
    """Legacy criterion for protected species."""

    choice_label = "EP > EP (obsolète)"
    slug = "ep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog

    def get_result_data(self):
        return "soumis"


class EspecesProtegeesSimple(EspecesProtegees):
    """Basic criterion: always returns "soumis."""

    choice_label = "EP > EP simple"
    slug = "ep_simple"


class EspecesProtegeesSettings(forms.Form):
    replantation_coefficient = forms.DecimalField(
        label="Coefficient de replantation",
        help_text="Coefficient « R » de replantation des haies",
        min_value=0,
        max_value=10,
        max_digits=4,
        decimal_places=1,
    )


class EspecesProtegeesAisne(CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Aisne"
    slug = "ep_aisne"
    settings_form_class = EspecesProtegeesSettings

    CODE_MATRIX = {
        (False, True): "interdit",
        (False, False): "interdit",
        (True, True): "derogation_inventaire",
        (True, False): "derogation_simplifiee",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "derogation_inventaire": RESULTS.derogation_inventaire,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            species = haies.get_all_species()
            catalog["protected_species"] = species
            catalog["fauna_sensitive_species"] = [
                s for s in species if s.highly_sensitive and s.kingdom == "animalia"
            ]
            catalog["flora_sensitive_species"] = [
                s for s in species if s.highly_sensitive and s.kingdom == "plantae"
            ]
        return catalog

    def get_result_data(self):
        has_reimplantation = self.catalog.get("reimplantation") != "non"
        has_sensitive_species = False
        species = self.catalog.get("protected_species")
        for s in species:
            if s.highly_sensitive:
                has_sensitive_species = True
                break

        return has_reimplantation, has_sensitive_species
