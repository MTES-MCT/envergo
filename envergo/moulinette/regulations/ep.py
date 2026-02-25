from collections import defaultdict
from decimal import Decimal as D

from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.core.validators import RegexValidator

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.models import HEDGE_TYPES, PACAGE_RE, Pacage
from envergo.hedges.regulations import (
    HEDGE_KEYS,
    EssencesBocageresCondition,
    LineaireInterchamp,
    LineaireSurTalusCondition,
    MinLengthCondition,
    NormandieQualityCondition,
    PlantationConditionMixin,
    QualityCondition,
    SafetyCondition,
    StrenghteningCondition,
)
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)
from envergo.utils.fields import get_human_readable_value


class EPRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > EP"

    PROCEDURE_TYPE_MATRIX = {
        "interdit": "interdit",
        "derogation": "autorisation",
        "derogation_simplifiee": "autorisation",
        "dispense_sous_condition": "declaration",
        "a_verifier": "declaration",
        "dispense": "declaration",
    }


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


def get_hedge_compensation_details(hedge, r):
    hedge_properties = []
    if hedge.prop("essences_non_bocageres"):
        hedge_properties.append("essences non bocagères")
    if hedge.prop("recemment_plantee"):
        hedge_properties.append("récemment plantée")
    if hedge.mode_destruction == "coupe_a_blanc":
        hedge_properties.append("coupe à blanc")
    if hedge.hedge_type == "alignement" and hedge.prop("bord_voie"):
        hedge_properties.append("L350-3")

    return {
        "id": hedge.id,
        "hedge_type": get_human_readable_value(HEDGE_TYPES, hedge.hedge_type),
        "properties": ", ".join(hedge_properties) if hedge_properties else "-",
        "length": hedge.length,
        "r": r,
    }


class EPNormandieForm(forms.Form):
    numero_pacage = forms.CharField(
        label="Quel est le numéro PACAGE de l'exploitation ?",
        required=True,
        validators=[
            RegexValidator(
                PACAGE_RE,
                message="Saisissez une valeur composée de 9 chiffres, sans espace.",
            )
        ],
        widget=forms.TextInput(attrs={"placeholder": "012345678"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial
        localisation_pac = data.get("localisation_pac")
        if localisation_pac == "non":
            self.fields = {}
            return


class EspecesProtegeesNormandie(
    PlantationConditionMixin, EPMixin, HedgeDensityMixin, CriterionEvaluator
):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Normandie"
    slug = "ep_normandie"
    plantation_conditions = [
        MinLengthCondition,
        SafetyCondition,
        StrenghteningCondition,
        LineaireSurTalusCondition,
        LineaireInterchamp,
        NormandieQualityCondition,
        EssencesBocageresCondition,
    ]
    form_class = EPNormandieForm

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
        "dispense_coupe_a_blanc": RESULTS.dispense_sous_condition,
        "dispense_20m": RESULTS.dispense_sous_condition,
        "dispense_10m": RESULTS.dispense,
        "dispense_L350": RESULTS.dispense_sous_condition,
        "dispense": RESULTS.dispense_sous_condition,
        "a_verifier_L350": RESULTS.a_verifier,
    }

    CODE_MATRIX = {
        ("0", True, False, "non"): "dispense_10m",
        ("0", True, False, "remplacement"): "dispense_10m",
        ("0", True, False, "replantation"): "dispense_10m",
        ("lte_1", True, False, "non"): "interdit",
        ("lte_1", True, False, "remplacement"): "dispense_20m",
        ("lte_1", True, False, "replantation"): "dispense_20m",
        ("gt_1", True, False, "non"): "interdit",
        ("gt_1", True, False, "remplacement"): "derogation_simplifiee",
        ("gt_1", True, False, "replantation"): "derogation_simplifiee",
        ("0", True, True, "non"): "dispense_10m",
        ("0", True, True, "remplacement"): "dispense_10m",
        ("0", True, True, "replantation"): "dispense_10m",
        ("lte_1", True, True, "non"): "interdit",
        ("lte_1", True, True, "remplacement"): "dispense_coupe_a_blanc",
        ("lte_1", True, True, "replantation"): "dispense_20m",
        ("gt_1", True, True, "non"): "interdit",
        ("gt_1", True, True, "remplacement"): "dispense_coupe_a_blanc",
        ("gt_1", True, True, "replantation"): "derogation_simplifiee",
        ("0", False, False, "non"): "dispense_10m",
        ("0", False, False, "remplacement"): "dispense_10m",
        ("0", False, False, "replantation"): "dispense_10m",
        ("lte_1", False, False, "non"): "interdit",
        ("lte_1", False, False, "remplacement"): "dispense",
        ("lte_1", False, False, "replantation"): "dispense",
        ("gt_1", False, False, "non"): "interdit",
        ("gt_1", False, False, "remplacement"): "derogation_simplifiee",
        ("gt_1", False, False, "replantation"): "derogation_simplifiee",
        ("0", False, True, "non"): "dispense_10m",
        ("0", False, True, "remplacement"): "dispense_10m",
        ("0", False, True, "replantation"): "dispense_10m",
        ("lte_1", False, True, "non"): "interdit",
        ("lte_1", False, True, "remplacement"): "dispense_coupe_a_blanc",
        ("lte_1", False, True, "replantation"): "dispense",
        ("gt_1", False, True, "non"): "interdit",
        ("gt_1", False, True, "remplacement"): "dispense_coupe_a_blanc",
        ("gt_1", False, True, "replantation"): "derogation_simplifiee",
    }

    COEFFICIENT_MATRIX = {
        ("degradee", "gt_1.6", "normandie_groupe_1"): D("1.2"),
        ("buissonnante", "gt_1.6", "normandie_groupe_1"): D("1.4"),
        ("arbustive", "gt_1.6", "normandie_groupe_1"): D("1.6"),
        ("alignement", "gt_1.6", "normandie_groupe_1"): D("1.6"),
        ("mixte", "gt_1.6", "normandie_groupe_1"): D("1.8"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_1"): D("1.4"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_1"): D("1.6"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_1"): D("1.8"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_1"): D("1.8"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_1"): D("2"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_1"): D("1.6"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_1"): D("1.8"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_1"): D("2"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_1"): D("2"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_1"): D("2.2"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_1"): D("1.8"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_1"): D("2"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_1"): D("2.5"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_1"): D("2.5"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_1"): D("3"),
        ("degradee", "lt_0.5", "normandie_groupe_1"): D("2.2"),
        ("buissonnante", "lt_0.5", "normandie_groupe_1"): D("2.6"),
        ("arbustive", "lt_0.5", "normandie_groupe_1"): D("3.2"),
        ("alignement", "lt_0.5", "normandie_groupe_1"): D("3.2"),
        ("mixte", "lt_0.5", "normandie_groupe_1"): D("3.5"),
        ("degradee", "gt_1.6", "normandie_groupe_2"): D("1"),
        ("buissonnante", "gt_1.6", "normandie_groupe_2"): D("1"),
        ("arbustive", "gt_1.6", "normandie_groupe_2"): D("1.4"),
        ("alignement", "gt_1.6", "normandie_groupe_2"): D("1.4"),
        ("mixte", "gt_1.6", "normandie_groupe_2"): D("1.6"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_2"): D("1.2"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_2"): D("1.4"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_2"): D("1.6"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_2"): D("1.6"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_2"): D("1.8"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_2"): D("1.4"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_2"): D("1.6"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_2"): D("1.8"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_2"): D("1.8"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_2"): D("2"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_2"): D("1.6"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_2"): D("1.8"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_2"): D("2"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_2"): D("2"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_2"): D("2.6"),
        ("degradee", "lt_0.5", "normandie_groupe_2"): D("2"),
        ("buissonnante", "lt_0.5", "normandie_groupe_2"): D("2.2"),
        ("arbustive", "lt_0.5", "normandie_groupe_2"): D("2.6"),
        ("alignement", "lt_0.5", "normandie_groupe_2"): D("2.6"),
        ("mixte", "lt_0.5", "normandie_groupe_2"): D("3.2"),
        ("degradee", "gt_1.6", "normandie_groupe_3"): D("1"),
        ("buissonnante", "gt_1.6", "normandie_groupe_3"): D("1"),
        ("arbustive", "gt_1.6", "normandie_groupe_3"): D("1"),
        ("alignement", "gt_1.6", "normandie_groupe_3"): D("1"),
        ("mixte", "gt_1.6", "normandie_groupe_3"): D("1.2"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_3"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_3"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_3"): D("1.2"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_3"): D("1.2"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_3"): D("1.4"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_3"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_3"): D("1.2"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_3"): D("1.4"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_3"): D("1.4"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_3"): D("1.6"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_3"): D("1.4"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_3"): D("1.6"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_3"): D("1.8"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_3"): D("1.8"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_3"): D("2.2"),
        ("degradee", "lt_0.5", "normandie_groupe_3"): D("1.8"),
        ("buissonnante", "lt_0.5", "normandie_groupe_3"): D("2"),
        ("arbustive", "lt_0.5", "normandie_groupe_3"): D("2.2"),
        ("alignement", "lt_0.5", "normandie_groupe_3"): D("2.2"),
        ("mixte", "lt_0.5", "normandie_groupe_3"): D("2.6"),
        ("degradee", "gt_1.6", "normandie_groupe_4"): D("1"),
        ("buissonnante", "gt_1.6", "normandie_groupe_4"): D("1"),
        ("arbustive", "gt_1.6", "normandie_groupe_4"): D("1"),
        ("alignement", "gt_1.6", "normandie_groupe_4"): D("1"),
        ("mixte", "gt_1.6", "normandie_groupe_4"): D("1"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_4"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_4"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_4"): D("1"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_4"): D("1"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_4"): D("1.2"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_4"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_4"): D("1"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_4"): D("1.2"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_4"): D("1.2"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_4"): D("1.4"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_4"): D("1.2"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_4"): D("1.4"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_4"): D("1.6"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_4"): D("1.6"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_4"): D("1.8"),
        ("degradee", "lt_0.5", "normandie_groupe_4"): D("1.6"),
        ("buissonnante", "lt_0.5", "normandie_groupe_4"): D("1.8"),
        ("arbustive", "lt_0.5", "normandie_groupe_4"): D("2"),
        ("alignement", "lt_0.5", "normandie_groupe_4"): D("2"),
        ("mixte", "lt_0.5", "normandie_groupe_4"): D("2.2"),
        ("degradee", "gt_1.6", "normandie_groupe_5"): D("1"),
        ("buissonnante", "gt_1.6", "normandie_groupe_5"): D("1"),
        ("arbustive", "gt_1.6", "normandie_groupe_5"): D("1"),
        ("alignement", "gt_1.6", "normandie_groupe_5"): D("1"),
        ("mixte", "gt_1.6", "normandie_groupe_5"): D("1"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_5"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_5"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_5"): D("1"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_5"): D("1"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_5"): D("1"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_5"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_5"): D("1"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_5"): D("1"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_5"): D("1"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_5"): D("1.2"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_5"): D("1"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_5"): D("1.2"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_5"): D("1.4"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_5"): D("1.4"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_5"): D("1.6"),
        ("degradee", "lt_0.5", "normandie_groupe_5"): D("1.4"),
        ("buissonnante", "lt_0.5", "normandie_groupe_5"): D("1.6"),
        ("arbustive", "lt_0.5", "normandie_groupe_5"): D("1.8"),
        ("alignement", "lt_0.5", "normandie_groupe_5"): D("1.8"),
        ("mixte", "lt_0.5", "normandie_groupe_5"): D("2"),
        ("degradee", "gt_1.6", "normandie_groupe_absent"): D("1"),
        ("buissonnante", "gt_1.6", "normandie_groupe_absent"): D("1"),
        ("arbustive", "gt_1.6", "normandie_groupe_absent"): D("1"),
        ("alignement", "gt_1.6", "normandie_groupe_absent"): D("1"),
        ("mixte", "gt_1.6", "normandie_groupe_absent"): D("1.2"),
        ("degradee", "gt_1.2_lte_1.6", "normandie_groupe_absent"): D("1"),
        ("buissonnante", "gt_1.2_lte_1.6", "normandie_groupe_absent"): D("1"),
        ("arbustive", "gt_1.2_lte_1.6", "normandie_groupe_absent"): D("1.2"),
        ("alignement", "gt_1.2_lte_1.6", "normandie_groupe_absent"): D("1.2"),
        ("mixte", "gt_1.2_lte_1.6", "normandie_groupe_absent"): D("1.4"),
        ("degradee", "gte_0.8_lte_1.2", "normandie_groupe_absent"): D("1"),
        ("buissonnante", "gte_0.8_lte_1.2", "normandie_groupe_absent"): D("1.2"),
        ("arbustive", "gte_0.8_lte_1.2", "normandie_groupe_absent"): D("1.4"),
        ("alignement", "gte_0.8_lte_1.2", "normandie_groupe_absent"): D("1.4"),
        ("mixte", "gte_0.8_lte_1.2", "normandie_groupe_absent"): D("1.6"),
        ("degradee", "gte_0.5_lt_0.8", "normandie_groupe_absent"): D("1.4"),
        ("buissonnante", "gte_0.5_lt_0.8", "normandie_groupe_absent"): D("1.6"),
        ("arbustive", "gte_0.5_lt_0.8", "normandie_groupe_absent"): D("1.8"),
        ("alignement", "gte_0.5_lt_0.8", "normandie_groupe_absent"): D("1.8"),
        ("mixte", "gte_0.5_lt_0.8", "normandie_groupe_absent"): D("2.2"),
        ("degradee", "lt_0.5", "normandie_groupe_absent"): D("1.8"),
        ("buissonnante", "lt_0.5", "normandie_groupe_absent"): D("2"),
        ("arbustive", "lt_0.5", "normandie_groupe_absent"): D("2.2"),
        ("alignement", "lt_0.5", "normandie_groupe_absent"): D("2.2"),
        ("mixte", "lt_0.5", "normandie_groupe_absent"): D("2.6"),
    }

    def get_exploitation_density(self, numero_pacage):
        if not numero_pacage:
            return None

        pacage = Pacage.objects.filter(pacage_num=numero_pacage).first()
        if pacage is None:
            densite = None
        else:
            densite = float(pacage.exploitation_density)

        return densite

    def get_catalog_data(self):
        catalog = super().get_catalog_data()

        haies = self.catalog.get("haies")
        all_r = []
        hedges_details = []
        coupe_a_blanc_every_hedge = True
        alignement_bord_voie_every_hedge = True
        lte_20m_every_hedge = True
        reimplantation = self.catalog.get("reimplantation")
        minimum_length_to_plant = D(0.0)
        aggregated_r = 0.0

        density_exploitation = self.get_exploitation_density(
            catalog.get("numero_pacage")
        )
        density_5000 = haies.density.get("around_centroid").get("density_5000")
        if density_exploitation:
            # If the density at 5km is 0, this means that we're in a hedge case (desert, sea, other?)
            # We then pick a coefficient corresponding to the Normandie average : 1
            density_ratio = (
                density_exploitation / density_5000 if density_5000 != 0 else 1.0
            )
        else:
            density_ratio = 1.0

        centroid_shapely = haies.get_centroid_to_remove()
        centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)

        # Normandie is divided into natural areas with a certain homogeneity of biodiversity.
        # We use the centroid of the hedges to find the zone in which the hedges are located.
        zonage = (
            Zone.objects.filter(
                geometry__contains=centroid_geos,
                map__map_type=MAP_TYPES.zonage,
            )
            .defer("geometry")
            .first()
        )

        # If the zone is not found, we use a default value for the zone_id.
        zone_id = (
            zonage.attributes.get("identifiant_zone", "normandie_groupe_absent")
            if zonage
            else "normandie_groupe_absent"
        )

        # Determine the density ratio range for coefficient lookup
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

        # Loop on the hedges to remove and calculate the replantation coefficient for each hedge.
        LD = defaultdict(int)  # linéaire à détruire
        LC = defaultdict(int)  # linéaire à compenser
        LPm_r = defaultdict(int)  # linéaire minimum attendu réduit

        for hedge in haies.hedges_to_remove():
            if hedge.mode_destruction != "coupe_a_blanc":
                coupe_a_blanc_every_hedge = False
            if hedge.hedge_type != "alignement" or not hedge.prop("bord_voie"):
                alignement_bord_voie_every_hedge = False

            if hedge.length > 20:
                lte_20m_every_hedge = False

            if hedge.length <= 10:
                r = D(0)
            elif hedge.prop("essences_non_bocageres"):
                r = D(1)
            else:
                if hedge.length <= 20:
                    r = D(1)
                elif (
                    reimplantation == "remplacement"
                    and hedge.mode_destruction == "coupe_a_blanc"
                ):
                    r = D(1)
                else:
                    r = self.COEFFICIENT_MATRIX[
                        (hedge.hedge_type, density_ratio_range, zone_id)
                    ]

            all_r.append(r)
            minimum_length_to_plant = D(minimum_length_to_plant) + D(hedge.length) * r
            hedges_details.append(get_hedge_compensation_details(hedge, r))

            # Note: if r == 0.0, the hedge does not need to be compensated, so it's
            # not added to the list of destroyed hedges
            if r > 0.0:
                LD[hedge.hedge_type] += hedge.length
                LC[hedge.hedge_type] += hedge.length * float(r)

        # Total compensation length before compensation reductions
        lpm = sum(LC.values())

        # Compensation can be reduced when planting a better type
        # Compensation rate cannot go below 1:1 though
        reduced_lpm = 0
        hedge_keys = HEDGE_KEYS.keys()
        for hedge_type in hedge_keys:
            lc_type = LC[hedge_type]
            lc_type *= 0.8 if hedge_type != "mixte" else 1.0
            lc_type = max(lc_type, LD[hedge_type])
            LPm_r[hedge_type] = lc_type
            reduced_lpm += lc_type

        catalog.update(
            {
                "LC": LC,
                "lpm": lpm,
                "reduced_lpm": reduced_lpm,
                "LPm_r": LPm_r,
            }
        )

        # Aggregate the R of each hedge to compute the global replantation coefficient.
        if haies.length_to_remove() > 0:
            aggregated_r = minimum_length_to_plant / D(haies.length_to_remove())

        r_max = max(all_r) if all_r else max(self.COEFFICIENT_MATRIX.values())
        catalog["r_max"] = r_max
        catalog["coupe_a_blanc_every_hedge"] = coupe_a_blanc_every_hedge
        catalog["alignement_bord_voie_every_hedge"] = alignement_bord_voie_every_hedge
        catalog["lte_20m_every_hedge"] = lte_20m_every_hedge
        catalog["aggregated_r"] = aggregated_r
        catalog["density_ratio"] = density_ratio
        catalog["density_5000"] = density_5000
        catalog["density_exploitation"] = density_exploitation
        catalog["density_zone"] = zone_id
        catalog["hedges_compensation_details"] = hedges_details
        return catalog

    def get_result_data(self):
        reimplantation = self.catalog.get("reimplantation")
        r_max = self.catalog.get("r_max")
        coupe_a_blanc_every_hedge = self.catalog.get("coupe_a_blanc_every_hedge")
        lte_20m_every_hedge = self.catalog.get("lte_20m_every_hedge")
        r_max_value = "0" if r_max == 0 else "lte_1" if r_max <= 1 else "gt_1"

        return (
            r_max_value,
            lte_20m_every_hedge,
            coupe_a_blanc_every_hedge,
            reimplantation,
        )

    def get_result_code(self, result_data):
        # this evaluator needs the result of the alignement_arbres criterion to get its own result
        # the regulation weight should be configurated to fetch the alignement_arbres before this one
        # if the alignement_arbres criterion is activated but has not been evaluated yet, it should raise an error
        if (
            self.catalog.get("alignement_bord_voie_every_hedge", False)
            and hasattr(self.moulinette, "alignement_arbres")
            and self.moulinette.alignement_arbres.is_activated
            and hasattr(self.moulinette.alignement_arbres, "alignement_arbres")
        ):
            if (
                self.moulinette.alignement_arbres.alignement_arbres.result_code
                == "soumis_securite"
            ):
                result = "dispense_L350"
            elif (
                self.moulinette.alignement_arbres.alignement_arbres.result_code
                == "soumis_esthetique"
            ):
                result = "a_verifier_L350"
            elif (
                self.moulinette.alignement_arbres.alignement_arbres.result_code
                == "soumis_autorisation"
            ):
                result = "a_verifier_L350"
            else:  # non soumis
                result = super().get_result_code(result_data)
        else:
            result = super().get_result_code(result_data)

        return result

    def get_replantation_coefficient(self):
        if self.result_code == "dispense_L350" or self.result_code == "a_verifier_L350":
            # If the result is "dispense_L350" or "a_verifier_L350", the replantation coefficient is 1.0
            return 1.0

        return self.catalog.get("aggregated_r")
