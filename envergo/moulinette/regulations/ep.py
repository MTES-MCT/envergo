from decimal import Decimal as D

from django.contrib.gis.geos import GEOSGeometry

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.regulations import (
    PlantationConditionMixin,
    QualityCondition,
    SafetyCondition,
)
from envergo.moulinette.regulations import CriterionEvaluator, HedgeDensityMixin


class EPMixin:
    """Legacy criterion for protected species."""

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog


class EspecesProtegeesSimple(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Basic criterion: always returns "soumis."""

    choice_label = "EP > EP simple"
    slug = "ep_simple"
    plantation_conditions = [SafetyCondition]

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"


class EspecesProtegeesAisne(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Aisne"
    slug = "ep_aisne"
    plantation_conditions = [SafetyCondition, QualityCondition]

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

    def get_replantation_coefficient(self):
        return D("1.5")


class EspecesProtegeesNormandie(
    PlantationConditionMixin, EPMixin, HedgeDensityMixin, CriterionEvaluator
):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Normandie"
    slug = "ep_normandie"
    plantation_conditions = [SafetyCondition]

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "interdit_remplacement": RESULTS.interdit,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
        "dispense_coupe_a_blanc": RESULTS.dispense_sous_condition,
        "dispense_20m": RESULTS.dispense_sous_condition,
        "dispense_10m": RESULTS.dispense,
    }

    CODE_MATRIX = {
        ("0", False, "non"): "dispense_10m",
        ("0", False, "remplacement"): "dispense_10m",
        ("0", False, "replantation"): "dispense_10m",
        ("lte_1", False, "non"): "interdit",
        ("lte_1", False, "remplacement"): "dispense_20m",
        ("lte_1", False, "replantation"): "dispense_20m",
        ("gt_1", False, "non"): "interdit",
        ("gt_1", False, "remplacement"): "interdit_remplacement",
        ("gt_1", False, "replantation"): "derogation_simplifiee",
        ("0", True, "non"): "dispense_10m",
        ("0", True, "remplacement"): "dispense_10m",
        ("0", True, "replantation"): "dispense_10m",
        ("lte_1", True, "non"): "interdit",
        ("lte_1", True, "remplacement"): "dispense_coupe_a_blanc",
        ("lte_1", True, "replantation"): "dispense_20m",
        ("gt_1", True, "non"): "interdit",
        ("gt_1", True, "remplacement"): "dispense_coupe_a_blanc",
        ("gt_1", True, "replantation"): "derogation_simplifiee",
    }

    COEFFICIENT_MATRIX = {
        ("degradee", "gt_1.6", "groupe_normandie_1"): D("1.2"),
        ("buissonnante", "gt_1.6", "groupe_normandie_1"): D("1.4"),
        ("arbustive", "gt_1.6", "groupe_normandie_1"): D("1.6"),
        ("alignement", "gt_1.6", "groupe_normandie_1"): D("1.6"),
        ("mixte", "gt_1.6", "groupe_normandie_1"): D("1.8"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_1"): D("1.4"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_1"): D("1.6"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_1"): D("1.8"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_1"): D("1.8"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_1"): D("2"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_1"): D("1.6"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_1"): D("1.8"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_1"): D("2"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_1"): D("2"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_1"): D("2.2"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_1"): D("1.8"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_1"): D("2"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_1"): D("2.5"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_1"): D("2.5"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_1"): D("3"),
        ("degradee", "lt_0.5", "groupe_normandie_1"): D("2.2"),
        ("buissonnante", "lt_0.5", "groupe_normandie_1"): D("2.6"),
        ("arbustive", "lt_0.5", "groupe_normandie_1"): D("3.2"),
        ("alignement", "lt_0.5", "groupe_normandie_1"): D("3.2"),
        ("mixte", "lt_0.5", "groupe_normandie_1"): D("3.5"),
        ("degradee", "gt_1.6", "groupe_normandie_2"): D("1"),
        ("buissonnante", "gt_1.6", "groupe_normandie_2"): D("1"),
        ("arbustive", "gt_1.6", "groupe_normandie_2"): D("1.4"),
        ("alignement", "gt_1.6", "groupe_normandie_2"): D("1.4"),
        ("mixte", "gt_1.6", "groupe_normandie_2"): D("1.6"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_2"): D("1.2"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_2"): D("1.4"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_2"): D("1.6"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_2"): D("1.6"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_2"): D("1.8"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_2"): D("1.4"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_2"): D("1.6"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_2"): D("1.8"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_2"): D("1.8"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_2"): D("2"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_2"): D("1.6"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_2"): D("1.8"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_2"): D("2"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_2"): D("2"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_2"): D("2.6"),
        ("degradee", "lt_0.5", "groupe_normandie_2"): D("2"),
        ("buissonnante", "lt_0.5", "groupe_normandie_2"): D("2.2"),
        ("arbustive", "lt_0.5", "groupe_normandie_2"): D("2.6"),
        ("alignement", "lt_0.5", "groupe_normandie_2"): D("2.6"),
        ("mixte", "lt_0.5", "groupe_normandie_2"): D("3.2"),
        ("degradee", "gt_1.6", "groupe_normandie_3"): D("1"),
        ("buissonnante", "gt_1.6", "groupe_normandie_3"): D("1"),
        ("arbustive", "gt_1.6", "groupe_normandie_3"): D("1"),
        ("alignement", "gt_1.6", "groupe_normandie_3"): D("1"),
        ("mixte", "gt_1.6", "groupe_normandie_3"): D("1.2"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_3"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_3"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_3"): D("1.2"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_3"): D("1.2"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_3"): D("1.4"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_3"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_3"): D("1.2"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_3"): D("1.4"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_3"): D("1.4"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_3"): D("1.6"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_3"): D("1.4"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_3"): D("1.6"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_3"): D("1.8"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_3"): D("1.8"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_3"): D("2.2"),
        ("degradee", "lt_0.5", "groupe_normandie_3"): D("1.8"),
        ("buissonnante", "lt_0.5", "groupe_normandie_3"): D("2"),
        ("arbustive", "lt_0.5", "groupe_normandie_3"): D("2.2"),
        ("alignement", "lt_0.5", "groupe_normandie_3"): D("2.2"),
        ("mixte", "lt_0.5", "groupe_normandie_3"): D("2.6"),
        ("degradee", "gt_1.6", "groupe_normandie_4"): D("1"),
        ("buissonnante", "gt_1.6", "groupe_normandie_4"): D("1"),
        ("arbustive", "gt_1.6", "groupe_normandie_4"): D("1"),
        ("alignement", "gt_1.6", "groupe_normandie_4"): D("1"),
        ("mixte", "gt_1.6", "groupe_normandie_4"): D("1"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_4"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_4"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_4"): D("1"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_4"): D("1"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_4"): D("1.2"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_4"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_4"): D("1"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_4"): D("1.2"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_4"): D("1.2"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_4"): D("1.4"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_4"): D("1.2"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_4"): D("1.4"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_4"): D("1.6"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_4"): D("1.6"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_4"): D("1.8"),
        ("degradee", "lt_0.5", "groupe_normandie_4"): D("1.6"),
        ("buissonnante", "lt_0.5", "groupe_normandie_4"): D("1.8"),
        ("arbustive", "lt_0.5", "groupe_normandie_4"): D("2"),
        ("alignement", "lt_0.5", "groupe_normandie_4"): D("2"),
        ("mixte", "lt_0.5", "groupe_normandie_4"): D("2.2"),
        ("degradee", "gt_1.6", "groupe_normandie_5"): D("1"),
        ("buissonnante", "gt_1.6", "groupe_normandie_5"): D("1"),
        ("arbustive", "gt_1.6", "groupe_normandie_5"): D("1"),
        ("alignement", "gt_1.6", "groupe_normandie_5"): D("1"),
        ("mixte", "gt_1.6", "groupe_normandie_5"): D("1"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_5"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_5"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_5"): D("1"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_5"): D("1"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_5"): D("1"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_5"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_5"): D("1"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_5"): D("1"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_5"): D("1"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_5"): D("1.2"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_5"): D("1"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_5"): D("1.2"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_5"): D("1.4"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_5"): D("1.4"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_5"): D("1.6"),
        ("degradee", "lt_0.5", "groupe_normandie_5"): D("1.4"),
        ("buissonnante", "lt_0.5", "groupe_normandie_5"): D("1.6"),
        ("arbustive", "lt_0.5", "groupe_normandie_5"): D("1.8"),
        ("alignement", "lt_0.5", "groupe_normandie_5"): D("1.8"),
        ("mixte", "lt_0.5", "groupe_normandie_5"): D("2"),
        ("degradee", "gt_1.6", "groupe_normandie_absent"): D("1"),
        ("buissonnante", "gt_1.6", "groupe_normandie_absent"): D("1"),
        ("arbustive", "gt_1.6", "groupe_normandie_absent"): D("1"),
        ("alignement", "gt_1.6", "groupe_normandie_absent"): D("1"),
        ("mixte", "gt_1.6", "groupe_normandie_absent"): D("1.2"),
        ("degradee", "gt_1.2_lte_1.6", "groupe_normandie_absent"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "groupe_normandie_absent"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "groupe_normandie_absent"): D("1.2"),
        ("alignement", "gt_1.2_lte_1.6", "groupe_normandie_absent"): D("1.2"),
        ("mixte", "gt_1.2_lte_1.6", "groupe_normandie_absent"): D("1.4"),
        ("degradee", "gte_0.8_lte_1.2", "groupe_normandie_absent"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "groupe_normandie_absent"): D("1.2"),
        ("arbustive", "gte_0.8_lte_1.2", "groupe_normandie_absent"): D("1.4"),
        ("alignement", "gte_0.8_lte_1.2", "groupe_normandie_absent"): D("1.4"),
        ("mixte", "gte_0.8_lte_1.2", "groupe_normandie_absent"): D("1.6"),
        ("degradee", "gte_0.5_lt_0.8", "groupe_normandie_absent"): D("1.4"),
        ("buissonnante", "gte_0.5_lt_0.8", "groupe_normandie_absent"): D("1.6"),
        ("arbustive", "gte_0.5_lt_0.8", "groupe_normandie_absent"): D("1.8"),
        ("alignement", "gte_0.5_lt_0.8", "groupe_normandie_absent"): D("1.8"),
        ("mixte", "gte_0.5_lt_0.8", "groupe_normandie_absent"): D("2.2"),
        ("degradee", "lt_0.5", "groupe_normandie_absent"): D("1.8"),
        ("buissonnante", "lt_0.5", "groupe_normandie_absent"): D("2"),
        ("arbustive", "lt_0.5", "groupe_normandie_absent"): D("2.2"),
        ("alignement", "lt_0.5", "groupe_normandie_absent"): D("2.2"),
        ("mixte", "lt_0.5", "groupe_normandie_absent"): D("2.6"),
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        all_r = []
        coupe_a_blanc_every_hedge = True
        reimplantation = self.catalog.get("reimplantation")
        minimum_length_to_plant = D(0.0)
        aggregated_r = 0.0

        density = haies.get_or_compute_density()
        density_200 = density.get("density_200")
        density_5000 = density.get("density_5000")

        centroid_shapely = haies.get_centroid_to_remove()
        centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)

        zonage = Zone.objects.filter(
            geometry__contains=centroid_geos,
            map__map_type=MAP_TYPES.zonage,
        ).first()

        zone_id = (
            zonage.attributes.get("indentifiant_zone", "groupe_normandie_absent")
            if zonage
            else "groupe_normandie_absent"
        )

        # If the density at 5km is 0, this means that we're in a hedge case (desert, sea, other?)
        # We then pick a coefficient corresponding to the Normandie average : 1
        density_ratio = density_200 / density_5000 if density_5000 != 0 else 1

        if density_ratio > 1.6:
            density_ratio_range = "gt_1.6"
        elif density_ratio > 1.2:
            density_ratio_range = "gt_1.2_lte_1.6"
        elif density_ratio >= 0.8:
            density_ratio_range = "gte_0.8_lte_1.2"
        elif density_ratio >= 0.5:
            density_ratio_range = "gte_0.5_lt_0.8"
        else:
            density_ratio_range = "lt_0.5"

        if haies:
            for hedge in haies.hedges_to_remove():
                if hedge.mode_destruction != "coupe_a_blanc":
                    coupe_a_blanc_every_hedge = False

                if hedge.length <= 10:
                    r = D(0)
                elif hedge.length <= 20:
                    r = D(1)
                elif (
                    reimplantation == "remplacement"
                    and hedge.mode_destruction == "coupe_a_blanc"
                ):
                    r = D(1)
                else:
                    r = self.COEFFICIENT_MATRIX.get(
                        (hedge.hedge_type, density_ratio_range, zone_id)
                    )

                if r is not None:
                    all_r.append(r)
                    minimum_length_to_plant = (
                        D(minimum_length_to_plant) + D(hedge.length) * r
                    )

            if haies.length_to_remove() > 0:
                aggregated_r = minimum_length_to_plant / D(haies.length_to_remove())

        r_max = max(all_r) if all_r else max(self.COEFFICIENT_MATRIX.values())
        catalog["r_max"] = r_max
        catalog["coupe_a_blanc_every_hedge"] = coupe_a_blanc_every_hedge
        catalog["aggregated_r"] = aggregated_r
        catalog["density_ratio"] = density_ratio
        catalog["density_zone"] = zone_id
        return catalog

    def get_result_data(self):
        reimplantation = self.catalog.get("reimplantation")
        r_max = self.catalog.get("r_max")
        coupe_a_blanc_every_hedge = self.catalog.get("coupe_a_blanc_every_hedge")
        r_max_value = "0" if r_max == 0 else "lte_1" if r_max <= 1 else "gt_1"

        return r_max_value, coupe_a_blanc_every_hedge, reimplantation

    def get_replantation_coefficient(self):
        return self.catalog.get("aggregated_r")
