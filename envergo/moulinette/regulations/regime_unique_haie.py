from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)


def compute_ru_compensation_ratio(moulinette):
    """Compute the régime unique compensation ratio.

    Returns the weighted average of per-hedge-type compensation coefficients
    (from the department config), weighted by hedge length. Alignements are
    excluded. Returns 0.0 when the department is not in régime unique.
    """
    if not moulinette.config.single_procedure:
        return 0.0

    haies = moulinette.catalog["haies"]
    coeff_by_type = moulinette.config.single_procedure_settings["coeff_compensation"]

    compensated_length = 0.0
    for hedge in haies.hedges_to_remove().n_alignement():
        compensated_length += hedge.length * coeff_by_type[hedge.hedge_type]

    return round(compensated_length / haies.length_to_remove(), 2)


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaie(PlantationConditionMixin, HedgeDensityMixin, CriterionEvaluator):
    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    plantation_conditions = []

    RESULT_MATRIX = {
        "non_concerne": RESULTS.non_concerne,
        "non_concerne_aa": RESULTS.non_concerne,
        "soumis": RESULTS.soumis,
    }

    CODE_MATRIX = {
        ("regime_unique", "aa_only"): "non_concerne_aa",
        ("regime_unique", "has_hedges"): "soumis",
        ("droit_constant", "aa_only"): "non_concerne",
        ("droit_constant", "has_hedges"): "non_concerne",
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies and self.moulinette.config.single_procedure:
            density_data = haies.density_around_lines
            catalog["density_400"] = density_data.get("density_400")
            catalog["density_400_length"] = density_data.get("length_400")
            catalog["density_400_area_ha"] = density_data.get("area_400_ha")
        return catalog

    def get_result_data(self):
        hedges = self.catalog["haies"].hedges_to_remove()
        has_hedges = any(h for h in hedges if h.hedge_type != "alignement")
        regime_unique = self.moulinette.config.single_procedure

        return "regime_unique" if regime_unique else "droit_constant", (
            "aa_only" if not has_hedges else "has_hedges"
        )

    def get_replantation_coefficient(self):
        return compute_ru_compensation_ratio(self.moulinette)
