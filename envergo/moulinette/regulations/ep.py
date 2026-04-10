from collections import defaultdict
from decimal import Decimal as D
from functools import cached_property
from math import ceil

import shapely
from django import forms
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import GEOSGeometry, MultiLineString
from django.core.validators import RegexValidator
from django.db.models.functions import Cast

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import MAP_TYPES, Zone
from envergo.geodata.utils import EPSG_WGS84
from envergo.hedges.models import PACAGE_RE, HedgeTypeFactory, Pacage
from envergo.hedges.regulations import (
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
from envergo.moulinette.regulations.regime_unique_haie import (
    compute_ru_compensation_ratio,
)
from envergo.utils.fields import get_human_readable_value


class EPRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > EP"

    PROCEDURE_TYPE_MATRIX = {
        "interdit": "interdit",
        "derogation_inventaire": "autorisation",
        "derogation_simplifiee": "autorisation",
        "dispense_sous_condition": "declaration",
        "a_verifier": "declaration",
        "dispense": "declaration",
        "non_concerne": "declaration",
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
        "hedge_type": get_human_readable_value(
            HedgeTypeFactory.build_from_context(single_procedure=False).choices,
            hedge.hedge_type,
        ),  # EP s'applique uniquement à "droit constant" pour le moment
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
    debug_template = "haie/moulinette/debug/ep_normandie.html"
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
        density_5000 = haies.density_around_centroid["density_5000"]
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

        HedgeType = HedgeTypeFactory.build_from_context(
            single_procedure=False
        )  # Cet évaluateur n'est utilisé qu'avant la mise en place du régime unique.
        for hedge_type in HedgeType.values:
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

    def get_debug_context(self):
        """Return centroid-based density data for debug display."""
        haies = self.catalog.get("haies")
        if not haies:
            return {}

        density_200, density_5000, centroid_geos = (
            haies.compute_density_around_points_with_artifacts()
        )
        # Pop circles from artifacts so they don't leak into the template context
        # dict, while keeping them available for the map builder below.
        truncated_circle_200 = density_200["artifacts"].pop("truncated_circle")
        truncated_circle_5000 = density_5000["artifacts"].pop("truncated_circle")

        context = {
            "numero_pacage": self.catalog.get("numero_pacage"),
            "density_exploitation": self.catalog.get("density_exploitation"),
            "density_5000": self.catalog.get("density_5000"),
            "density_ratio": self.catalog.get("density_ratio"),
            "density_zone": self.catalog.get("density_zone"),
            "length_200": density_200["artifacts"]["length"],
            "length_5000": density_5000["artifacts"]["length"],
            "area_200_ha": density_200["artifacts"]["area_ha"],
            "area_5000_ha": density_5000["artifacts"]["area_ha"],
            "density_200": density_200["density"],
            "debug_density_5000": density_5000["density"],
        }

        pre_computed = haies.density_around_centroid
        if pre_computed:
            context["pre_computed_density_200"] = pre_computed["density_200"]
            context["pre_computed_density_5000"] = pre_computed["density_5000"]

        from envergo.hedges.services import create_density_map

        context["density_map"] = create_density_map(
            centroid_geos,
            haies.hedges_to_remove(),
            truncated_circle_200,
            truncated_circle_5000,
        )
        return context


class EspecesProtegeesRegimeUniqueSettings(forms.Form):
    """Configurable thresholds for the EP régime unique cascade algorithm.

    All thresholds are required: missing or invalid values cause the
    criterion to evaluate to ``non_disponible`` (the admin must populate
    them per criterion).
    """

    l_ripisylve = forms.IntegerField(
        label="L_ripisylve (m)",
        help_text=(
            "Seuil de longueur de ripisylve détruite au-delà duquel "
            "le projet bascule en dérogation standard."
        ),
        required=True,
        min_value=0,
    )
    l_bas = forms.IntegerField(
        label="L_bas (m)",
        help_text=(
            "Seuil bas de longueur totale détruite : en deçà, le projet "
            "obtient une dispense."
        ),
        required=True,
        min_value=0,
    )
    l_haut = forms.IntegerField(
        label="L_haut (m)",
        help_text=(
            "Seuil haut de longueur totale détruite : au-delà, le projet "
            "est considéré comme à fort impact."
        ),
        required=True,
        min_value=0,
    )
    d_bas = forms.IntegerField(
        label="D_bas (ml/ha)",
        help_text="Seuil bas de densité bocagère (mètres linéaires par hectare).",
        required=True,
        min_value=0,
    )
    d_haut = forms.IntegerField(
        label="D_haut (ml/ha)",
        help_text="Seuil haut de densité bocagère (mètres linéaires par hectare).",
        required=True,
        min_value=0,
    )

    def clean(self):
        cleaned = super().clean()
        l_bas = cleaned.get("l_bas")
        l_haut = cleaned.get("l_haut")
        d_bas = cleaned.get("d_bas")
        d_haut = cleaned.get("d_haut")
        if l_bas is not None and l_haut is not None and l_bas > l_haut:
            raise forms.ValidationError("L_bas doit être inférieur ou égal à L_haut.")
        if d_bas is not None and d_haut is not None and d_bas > d_haut:
            raise forms.ValidationError("D_bas doit être inférieur ou égal à D_haut.")
        return cleaned


# Severity ranking used to pick the most constraining per-hedge result.
EP_RU_RESULT_RANK = {
    "dispense": 1,
    "derogation_simplifiee": 2,
    "derogation_inventaire": 3,
}

# Replantation coefficient bonus per result level (added to R_ru).
EP_RU_REPLANTATION_BONUS = {
    "derogation_inventaire": 0.5,
    "derogation_simplifiee": 0.25,
    "dispense": 0.0,
}


class EspecesProtegeesRegimeUnique(
    PlantationConditionMixin, EPMixin, HedgeDensityMixin, CriterionEvaluator
):
    """EP criterion for the "régime unique" procedure.

    Determines the required procedure level (dispense / dérogation simplifiée /
    dérogation with field inventory) based on hedge lengths, riparian status,
    bocage density and sensitive-zone intersection.
    """

    choice_label = "EP > EP Régime unique"
    slug = "ep_regime_unique"
    debug_template = "haie/moulinette/debug/ep_regime_unique.html"
    plantation_conditions = []
    form_class = None
    settings_form_class = EspecesProtegeesRegimeUniqueSettings

    RESULT_MATRIX = {
        "non_concerne": RESULTS.non_concerne,
        "dispense": RESULTS.dispense,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
        "derogation_inventaire": RESULTS.derogation_inventaire,
    }

    @cached_property
    def params(self):
        """Validated, typed threshold settings.

        Returns ``None`` when the admin-supplied settings are missing or
        invalid; in that case the criterion is reported as ``non_disponible``
        by ``CriterionEvaluator.evaluate`` (which re-validates the form),
        and methods that need the thresholds simply bail out.
        """
        form = self.get_settings_form()
        if form is None or not form.is_valid():
            return None
        return form.cleaned_data

    def get_hedges_in_zone_sensible(self, hedges):
        """Return the set of hedge IDs that intersect a "Zone sensible EP" map.

        Aggregates all matching zones into a single multipolygon, then tests
        each hedge for intersection in Python (shapely).
        """
        if not hedges:
            return set()

        hedges_geom = MultiLineString(
            [h.geos_geometry for h in hedges], srid=EPSG_WGS84
        )
        qs = Zone.objects.filter(
            map__map_type=MAP_TYPES.zone_sensible_ep,
            geometry__intersects=hedges_geom,
        ).aggregate(geom=Union(Cast("geometry", MultiPolygonField())))
        multipolygon = qs["geom"]

        if not multipolygon:
            return set()

        geom = shapely.from_wkt(multipolygon.wkt)
        result = set()
        for h in hedges:
            intersection = h.geometry.intersection(geom)
            if not intersection.is_empty:
                result.add(h.id)
        return result

    def get_catalog_data(self):
        """Populate the catalog with EP régime unique inputs.

        Computes hedge lengths, ripisylve length, zone sensible flags,
        line-buffer density, and per-hedge procedure-level results.

        When the admin-supplied threshold settings are missing or invalid,
        per-hedge results are skipped: the criterion is going to be
        reported as ``non_disponible`` by ``evaluate()`` regardless, so
        bailing out keeps the catalog free of meaningless values.
        """
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if not haies:
            return catalog

        # Line-buffer density (400 m)
        density_data = haies.density_around_lines
        catalog["density_400"] = density_data.get("density_400")
        catalog["density_400_length"] = density_data.get("length_400")
        catalog["density_400_area_ha"] = density_data.get("area_400_ha")

        hedges = haies.hedges_to_remove().n_alignement()

        catalog["ep_ru_aa_only"] = not hedges

        # Total length and ripisylve length (excluding alignements)
        total_length = hedges.length
        ripisylve_length = hedges.filter(lambda h: h.prop("ripisylve")).length
        catalog["ep_ru_total_length"] = ceil(total_length)
        catalog["ep_ru_ripisylve_length"] = ceil(ripisylve_length)

        hedges_in_zone_sensible = self.get_hedges_in_zone_sensible(hedges)
        catalog["ep_ru_zone_sensible"] = hedges_in_zone_sensible

        # Treat missing density (None) as zero — low density steers the cascade
        # toward more constraining procedure levels when data is unavailable.
        density = catalog.get("density_400")
        if density is None:
            density = 0
        catalog["ep_ru_density"] = density

        params = self.params
        if params is None:
            return catalog

        catalog["ep_ru_per_hedge_results"] = self.compute_per_hedge_results(
            hedges,
            catalog["ep_ru_total_length"],
            density,
            hedges_in_zone_sensible,
            l_haut=params["l_haut"],
            d_haut=params["d_haut"],
        )

        return catalog

    def compute_per_hedge_results(
        self, hedges, total_length, density, hedges_in_zone_sensible, l_haut, d_haut
    ):
        """Assign a procedure level to each hedge based on length, density, type and zone.

        Only meaningful when the project-level cascade falls through to
        step 6 (per-hedge evaluation). Called unconditionally so the debug
        view always has data to display.

        Args:
            hedges: iterable of non-alignement hedges to classify.
            total_length: total length of the destruction project (m).
            density: project-wide bocage density (ml/ha).
            hedges_in_zone_sensible: set of hedge ids intersecting a zone sensible.
            l_haut: high length threshold (m), from settings.
            d_haut: high density threshold (ml/ha), from settings.
        """
        per_hedge_results = {}
        for h in hedges:
            in_zone = h.id in hedges_in_zone_sensible
            is_mixte = h.hedge_type == "mixte"
            long_total = total_length > l_haut
            high_density = density > d_haut

            if long_total and in_zone:
                result = "derogation_inventaire"
            elif high_density and not long_total and not is_mixte and not in_zone:
                result = "dispense"
            else:
                result = "derogation_simplifiee"

            per_hedge_results[h.id] = result
        return per_hedge_results

    def get_result_data(self):
        """Return project-level EP parameters for the cascade algorithm."""
        return {
            "is_regime_unique": self.moulinette.config.single_procedure,
            "aa_only": self.catalog.get("ep_ru_aa_only", False),
            "total_length": self.catalog.get("ep_ru_total_length", 0),
            "ripisylve_length": self.catalog.get("ep_ru_ripisylve_length", 0),
            "density": self.catalog.get("ep_ru_density", 0),
            "per_hedge_results": self.catalog.get("ep_ru_per_hedge_results", {}),
        }

    def get_result_code(self, result_data):
        """Cascade algorithm for the EP régime unique procedure level.

        Project-level rules (steps 0-5) are tried first. If none match, the
        most constraining per-hedge result wins (step 6). All thresholds
        come from the admin-configurable settings (validated by
        ``EspecesProtegeesRegimeUniqueSettings``); ``self.params`` is
        guaranteed non-None here because ``evaluate()`` short-circuits to
        ``non_disponible`` whenever the form is invalid.
        """
        # 0. Department not in régime unique → not concerned
        if not result_data["is_regime_unique"]:
            return "non_concerne"

        aa_only = result_data["aa_only"]
        total_length = result_data["total_length"]
        ripisylve_length = result_data["ripisylve_length"]
        density = result_data["density"]
        per_hedge_results = result_data["per_hedge_results"]

        params = self.params
        l_ripisylve = params["l_ripisylve"]
        l_bas = params["l_bas"]
        l_haut = params["l_haut"]
        d_bas = params["d_bas"]
        d_haut = params["d_haut"]

        # 1. Only tree-row hedges
        if aa_only:
            result = "derogation_inventaire"
        # 2. Ripisylve threshold exceeded
        elif ripisylve_length > l_ripisylve:
            result = "derogation_inventaire"
        # 3. Very short total
        elif total_length <= l_bas:
            result = "dispense"
        # 4. Medium total with moderate density
        elif total_length <= l_haut and density < d_haut:
            result = "derogation_simplifiee"
        # 5. Long total with low density
        elif total_length > l_haut and density < d_bas:
            result = "derogation_inventaire"
        # 6. Per-hedge evaluation — pick the most constraining
        else:
            result = max(per_hedge_results.values(), key=lambda r: EP_RU_RESULT_RANK[r])

        return result

    def get_replantation_coefficient(self):
        """Base RU coefficient plus a bonus depending on the EP result level."""
        r_ru = compute_ru_compensation_ratio(self.moulinette)
        bonus = EP_RU_REPLANTATION_BONUS.get(self.result_code, 0.0)
        return round(r_ru + bonus, 2)

    def build_hedge_rows(self):
        """Build per-hedge display rows for non-alignement hedges.

        Returns a list of dicts with id, hedge_type (human-readable), and
        in_zone_sensible — used by both the debug page and the instructor view.
        """
        haies = self.catalog.get("haies")
        if not haies:
            return []

        hedges_in_zone_sensible = self.catalog.get("ep_ru_zone_sensible", set())
        hedges = haies.hedges_to_remove().n_alignement()
        HedgeType = HedgeTypeFactory.build_from_context(single_procedure=True)

        rows = []
        for h in hedges:
            rows.append(
                {
                    "id": h.id,
                    "hedge_type": get_human_readable_value(
                        HedgeType.choices, h.hedge_type
                    ),
                    "in_zone_sensible": h.id in hedges_in_zone_sensible,
                }
            )
        return rows

    def get_debug_context(self):
        """Return density + EP-specific debug data."""
        context = super().get_debug_context()

        per_hedge_results = self.catalog.get("ep_ru_per_hedge_results", {})
        hedge_rows = self.build_hedge_rows()
        for row in hedge_rows:
            row["partial_result"] = per_hedge_results.get(row["id"], "-")

        context["ep_ru_total_length"] = self.catalog.get("ep_ru_total_length")
        context["ep_ru_ripisylve_length"] = self.catalog.get("ep_ru_ripisylve_length")
        context["hedge_debug_rows"] = hedge_rows
        # Surface the admin-configured thresholds so the debug page shows
        # exactly which values drove the cascade. None when settings are
        # missing/invalid — the template hides the table in that case.
        context["ep_ru_settings"] = self.params
        return context
