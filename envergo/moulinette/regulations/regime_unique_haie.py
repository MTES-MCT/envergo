from collections import defaultdict

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaie(PlantationConditionMixin, HedgeDensityMixin, CriterionEvaluator):
    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    debug_template = "haie/moulinette/debug/density_around_lines.html"
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
            density_data = haies.density.get("around_lines", {})
            catalog["density_400"] = density_data.get("density_400")
            catalog["density_400_length"] = density_data.get("length_400")
            catalog["density_400_area_ha"] = density_data.get("area_400_ha")
        return catalog

    def get_debug_context(self):
        """Return line-buffer density data for debug display."""
        haies = self.catalog.get("haies")
        if not haies:
            return {}

        density_400 = haies.compute_density_around_lines_with_artifacts()
        context = {
            "density_400": density_400["density"],
            "density_400_length": density_400["artifacts"]["length"],
            "density_400_area_ha": density_400["artifacts"]["area_ha"],
            "haies_id": haies.id,
        }

        pre_computed = haies.density.get("around_lines", {})
        if pre_computed:
            context["pre_computed_density_400"] = pre_computed.get("density_400")

        from envergo.hedges.services import create_line_buffer_density_map

        context["density_map"] = create_line_buffer_density_map(
            haies.hedges_to_remove(),
            density_400["artifacts"]["truncated_buffer_zone"],
            density_400["artifacts"]["buffer_zone"],
        )

        return context

    def get_result_data(self):
        hedges = self.catalog["haies"].hedges_to_remove()
        has_hedges = any(h for h in hedges if h.hedge_type != "alignement")
        regime_unique = self.moulinette.config.single_procedure

        return "regime_unique" if regime_unique else "droit_constant", (
            "aa_only" if not has_hedges else "has_hedges"
        )

    def get_replantation_coefficient(self):
        if not self.moulinette.config.single_procedure:
            return 0.0

        haies = self.catalog["haies"]
        minimum_length_to_plant = 0.0
        lengths_by_type = defaultdict(int)
        for to_remove in haies.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        for hedge_type, length in lengths_by_type.items():
            if hedge_type == "alignement":
                continue

            coeff = self.moulinette.config.single_procedure_settings[
                "coeff_compensation"
            ][hedge_type]
            minimum_length_to_plant += length * coeff

        R = minimum_length_to_plant / haies.length_to_remove()
        return round(R, 2)
