import logging

from envergo.evaluations.models import RESULTS
from envergo.geodata.utils import get_catchment_area
from envergo.moulinette.regulations import (
    ActionsToTakeMixin,
    AmenagementRegulationEvaluator,
    CriterionEvaluator,
    Map,
    MapPolygon,
    SelfDeclarationMixin,
)
from envergo.moulinette.regulations.mixins import ZoneHumideMixin, ZoneInondableMixin

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"
PINK = "#FF9575"


logger = logging.getLogger(__name__)


class LoiSurLEauRegulation(ActionsToTakeMixin, AmenagementRegulationEvaluator):
    choice_label = "Aménagement > Loi sur l'eau"

    ACTIONS_TO_TAKE_MATRIX = {
        "soumis_ou_pac": ["depot_pac_lse", "mention_arrete_lse"],
        "soumis": ["depot_dossier_lse", "mention_arrete_lse", "pc_ein"],
        "action_requise": ["mention_arrete_lse"],
    }


class ZoneHumide(
    ZoneHumideMixin,
    SelfDeclarationMixin,
    ActionsToTakeMixin,
    CriterionEvaluator,
):
    choice_label = "Loi sur l'eau > Zone humide"
    slug = "zone_humide"

    CODES = [
        "soumis",
        "non_soumis",
        "non_concerne",
        "action_requise",
        "action_requise_proche",
        "action_requise_dans_doute",
        "action_requise_tout_dpt",
    ]

    CODE_MATRIX = {
        ("inside", "big"): "soumis",
        ("inside", "medium"): "action_requise",
        ("inside", "small"): "non_soumis",
        ("close_to", "big"): "action_requise_proche",
        ("close_to", "medium"): "non_soumis",
        ("close_to", "small"): "non_soumis",
        ("inside_potential", "big"): "action_requise_dans_doute",
        ("inside_potential", "medium"): "non_soumis",
        ("inside_potential", "small"): "non_soumis",
        ("inside_wetlands_dpt", "big"): "action_requise_tout_dpt",
        ("inside_wetlands_dpt", "medium"): "non_soumis",
        ("inside_wetlands_dpt", "small"): "non_soumis",
        ("outside", "big"): "non_concerne",
        ("outside", "medium"): "non_concerne",
        ("outside", "small"): "non_concerne",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_soumis": RESULTS.non_soumis,
        "non_concerne": RESULTS.non_concerne,
        "action_requise": RESULTS.action_requise,
        "action_requise_proche": RESULTS.action_requise,
        "action_requise_dans_doute": RESULTS.action_requise,
        "action_requise_tout_dpt": RESULTS.action_requise,
    }

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": ["etude_zh"]}

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_10m"]:
            wetland_status = "inside_potential"
        elif self.catalog["within_potential_wetlands_department"]:
            wetland_status = "inside_wetlands_dpt"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= 1000:
            project_size = "big"
        elif self.catalog["created_surface"] >= 700:
            project_size = "medium"
        else:
            project_size = "small"

        return wetland_status, project_size

    def get_map(self):
        map_polygons = []

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

        wetlands_qs = [
            zone for zone in self.catalog["wetlands"] if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLUE, "Zone humide"))

        if self.catalog["wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and not self.catalog["potential_wetlands_within_10m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and self.catalog["potential_wetlands_within_10m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_10m"] and potential_qs:
            caption = "Le projet se situe dans une zone humide potentielle."
        else:
            if self.result_code == "action_requise_tout_dpt":
                caption = """
                    Le projet se situe hors des zones humides listées dans les cartographies
                    existantes. Cependant, seul un inventaire de terrain à la parcelle permet
                    d'écarter la présence d'une zone humide (doctrine DDT(M) du département).
                """
            else:
                caption = "Le projet ne se situe pas dans une zone humide référencée."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["lng_lat"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class ZoneInondable(
    ZoneInondableMixin,
    SelfDeclarationMixin,
    ActionsToTakeMixin,
    CriterionEvaluator,
):
    choice_label = "Loi sur l'eau > Zone inondable"
    slug = "zone_inondable"

    CODES = ["soumis", "soumis_ou_pac", "action_requise", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        ("inside", "new_big"): "soumis",
        ("inside", "big"): "soumis_ou_pac",
        ("inside", "medium"): "action_requise",
        ("inside", "small"): "non_soumis",
        ("inside_potential", "new_big"): "action_requise_dans_doute",
        ("inside_potential", "big"): "action_requise_dans_doute",
        ("inside_potential", "medium"): "non_soumis",
        ("inside_potential", "small"): "non_soumis",
        ("outside", "new_big"): "non_concerne",
        ("outside", "big"): "non_concerne",
        ("outside", "medium"): "non_concerne",
        ("outside", "small"): "non_concerne",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "soumis_ou_pac": RESULTS.soumis_ou_pac,
        "non_soumis": RESULTS.non_soumis,
        "non_concerne": RESULTS.non_concerne,
        "action_requise": RESULTS.action_requise,
        "action_requise_dans_doute": RESULTS.action_requise,
    }

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": ["etude_zi_lse"]}

    def get_result_data(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        elif self.catalog["potential_flood_zones_within_0m"]:
            flood_zone_status = "inside_potential"
        else:
            flood_zone_status = "outside"

        if (
            self.catalog["final_surface"] >= 400
            and self.catalog["existing_surface"] >= 400
        ):
            project_size = "big"
        elif self.catalog["final_surface"] >= 400:
            project_size = "new_big"
        elif self.catalog["final_surface"] >= 300:
            project_size = "medium"
        else:
            project_size = "small"

        return flood_zone_status, project_size

    def get_map(self):
        map_polygons = []

        potential_qs = [
            zone
            for zone in self.catalog["potential_flood_zones"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, PINK, "Zone inondable potentielle")
            )

        zone_qs = [
            zone for zone in self.catalog["flood_zones"] if zone.map.display_for_user
        ]
        if zone_qs:
            map_polygons.append(MapPolygon(zone_qs, "red", "Zone inondable"))

        if self.catalog["flood_zones_within_12m"]:
            caption = "Le projet se situe dans une zone inondable."
        elif self.catalog["potential_flood_zones_within_0m"]:
            caption = "Le projet se situe dans une zone inondable potentielle."
        else:
            caption = "Le projet ne se situe pas en zone inondable."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["lng_lat"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class EcoulementSansBV(SelfDeclarationMixin, ActionsToTakeMixin, CriterionEvaluator):
    choice_label = "Loi sur l'eau > Écoulement EP sans BV"
    slug = "ecoulement_sans_bv"

    CODES = [
        "soumis",
        "soumis_ou_pac",
        "action_requise",
        "non_soumis",
        "action_requise_pv_sol",
        "non_soumis_pv_sol",
    ]

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "soumis_ou_pac": RESULTS.soumis_ou_pac,
        "action_requise_pv_sol": RESULTS.action_requise,
        "action_requise": RESULTS.action_requise,
        "non_soumis_pv_sol": RESULTS.non_soumis,
        "non_soumis": RESULTS.non_soumis,
    }

    CODE_MATRIX = {
        ("gte_1ha_new", "non_pv_sol"): "soumis",
        ("gte_1ha", "non_pv_sol"): "soumis_ou_pac",
        ("gte_9000", "non_pv_sol"): "action_requise",
        ("gte_8000", "non_pv_sol"): "action_requise",
        ("lt_8000", "non_pv_sol"): "non_soumis",
        ("gte_1ha_new", "pv_sol"): "action_requise_pv_sol",
        ("gte_1ha", "pv_sol"): "action_requise_pv_sol",
        ("gte_9000", "pv_sol"): "action_requise_pv_sol",
        ("gte_8000", "pv_sol"): "non_soumis_pv_sol",
        ("lt_8000", "pv_sol"): "non_soumis_pv_sol",
    }

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": ["etude_2150"]}

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["existing_surface"] = (
            self.catalog["final_surface"] - self.catalog["created_surface"]
        )
        return data

    def get_result_data(self):
        if (
            self.catalog["final_surface"] >= 10000
            and self.catalog["existing_surface"] >= 10000
        ):
            final_surface = "gte_1ha_new"
        if self.catalog["final_surface"] >= 10000:
            final_surface = "gte_1ha"
        elif self.catalog["final_surface"] >= 9000:
            final_surface = "gte_9000"
        elif self.catalog["final_surface"] >= 8000:
            final_surface = "gte_8000"
        else:
            final_surface = "lt_8000"

        is_pv_sol = "non_pv_sol"
        if self.moulinette.data.get("evalenv_rubrique_30-localisation") == "sol":
            is_pv_sol = "pv_sol"

        return final_surface, is_pv_sol


# This was the old evaluator name
# it has to stay here for compatibility reasons
class Ruissellement(EcoulementSansBV):
    choice_label = "Loi sur l'eau > Ruissellement (obsolète)"


class EcoulementAvecBV(SelfDeclarationMixin, ActionsToTakeMixin, CriterionEvaluator):
    choice_label = "Loi sur l'eau > Écoulement EP avec BV"
    slug = "ecoulement_avec_bv"

    CODES = [
        "soumis",
        "soumis_ou_pac",
        "action_requise_probable_1ha",
        "action_requise",
        "non_soumis",
        "action_requise_pv_sol",
        "non_soumis_pv_sol",
    ]

    CODE_MATRIX = {
        ("existing_gte_10000", "gt_11000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        (
            "existing_gte_10000",
            "gt_11000",
            "gt_9000",
            "pv_sol",
        ): "action_requise_pv_sol",
        ("existing_gte_10000", "gt_11000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_11000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_11000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_9000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        ("existing_gte_10000", "gt_9000", "gt_9000", "pv_sol"): "action_requise_pv_sol",
        ("existing_gte_10000", "gt_9000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_9000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_9000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "lt_9000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        ("existing_gte_10000", "lt_9000", "gt_9000", "pv_sol"): "action_requise_pv_sol",
        ("existing_gte_10000", "lt_9000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "lt_9000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "lt_9000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_gte_10000", "gt_11000", "gt_1ha", "non_pv_sol"): "soumis_ou_pac",
        (
            "existing_gte_10000",
            "gt_11000",
            "gt_9000",
            "non_pv_sol",
        ): "action_requise_probable_1ha",
        (
            "existing_gte_10000",
            "gt_11000",
            "gt_7000",
            "non_pv_sol",
        ): "action_requise_probable_1ha",
        ("existing_gte_10000", "gt_11000", "gt_1500", "non_pv_sol"): "action_requise",
        ("existing_gte_10000", "gt_11000", "lt_1500", "non_pv_sol"): "non_soumis",
        ("existing_gte_10000", "gt_9000", "gt_1ha", "non_pv_sol"): "soumis_ou_pac",
        ("existing_gte_10000", "gt_9000", "gt_9000", "non_pv_sol"): "action_requise",
        ("existing_gte_10000", "gt_9000", "gt_7000", "non_pv_sol"): "action_requise",
        ("existing_gte_10000", "gt_9000", "gt_1500", "non_pv_sol"): "action_requise",
        ("existing_gte_10000", "gt_9000", "lt_1500", "non_pv_sol"): "non_soumis",
        ("existing_gte_10000", "lt_9000", "gt_1ha", "non_pv_sol"): "soumis",
        ("existing_gte_10000", "lt_9000", "gt_9000", "non_pv_sol"): "non_soumis",
        ("existing_gte_10000", "lt_9000", "gt_7000", "non_pv_sol"): "non_soumis",
        ("existing_gte_10000", "lt_9000", "gt_1500", "non_pv_sol"): "non_soumis",
        ("existing_gte_10000", "lt_9000", "lt_1500", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "gt_11000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "gt_11000", "gt_9000", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "gt_11000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_11000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_11000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_9000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "gt_9000", "gt_9000", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "gt_9000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_9000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_9000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "lt_9000", "gt_1ha", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "lt_9000", "gt_9000", "pv_sol"): "action_requise_pv_sol",
        ("existing_lt_10000", "lt_9000", "gt_7000", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "lt_9000", "gt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "lt_9000", "lt_1500", "pv_sol"): "non_soumis_pv_sol",
        ("existing_lt_10000", "gt_11000", "gt_1ha", "non_pv_sol"): "soumis",
        (
            "existing_lt_10000",
            "gt_11000",
            "gt_9000",
            "non_pv_sol",
        ): "action_requise_probable_1ha",
        (
            "existing_lt_10000",
            "gt_11000",
            "gt_7000",
            "non_pv_sol",
        ): "action_requise_probable_1ha",
        ("existing_lt_10000", "gt_11000", "gt_1500", "non_pv_sol"): "action_requise",
        ("existing_lt_10000", "gt_11000", "lt_1500", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "gt_9000", "gt_1ha", "non_pv_sol"): "soumis",
        ("existing_lt_10000", "gt_9000", "gt_9000", "non_pv_sol"): "action_requise",
        ("existing_lt_10000", "gt_9000", "gt_7000", "non_pv_sol"): "action_requise",
        ("existing_lt_10000", "gt_9000", "gt_1500", "non_pv_sol"): "action_requise",
        ("existing_lt_10000", "gt_9000", "lt_1500", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "lt_9000", "gt_1ha", "non_pv_sol"): "soumis",
        ("existing_lt_10000", "lt_9000", "gt_9000", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "lt_9000", "gt_7000", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "lt_9000", "gt_1500", "non_pv_sol"): "non_soumis",
        ("existing_lt_10000", "lt_9000", "lt_1500", "non_pv_sol"): "non_soumis",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "soumis_ou_pac": RESULTS.soumis_ou_pac,
        "action_requise_probable_1ha": RESULTS.action_requise,
        "action_requise_pv_sol": RESULTS.action_requise,
        "action_requise": RESULTS.action_requise,
        "non_soumis_pv_sol": RESULTS.non_soumis,
        "non_soumis": RESULTS.non_soumis,
    }

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": ["etude_2150"]}

    def get_catalog_data(self):
        data = {}

        # If we cannot compute the catchment area surface, we have to consider
        # the value is 0
        surface = get_catchment_area(self.catalog["lng"], self.catalog["lat"])
        if surface is None:
            surface = 0
            logger.error(
                f"Pas de données bassin versant {self.catalog['lng']}, {self.catalog['lat']}"
            )
        surface = round(surface / 500) * 500
        total_surface = surface + self.catalog["final_surface"]

        data["catchment_surface"] = surface
        data["total_catchment_surface"] = total_surface

        data["existing_surface"] = (
            self.catalog["final_surface"] - self.catalog["created_surface"]
        )
        return data

    def get_result_data(self):
        if self.catalog["final_surface"] >= 10000:
            final_surface = "gt_1ha"
        elif self.catalog["final_surface"] >= 9000:
            final_surface = "gt_9000"
        elif self.catalog["final_surface"] >= 7000:
            final_surface = "gt_7000"
        elif self.catalog["final_surface"] >= 1500:
            final_surface = "gt_1500"
        else:
            final_surface = "lt_1500"

        if self.catalog["total_catchment_surface"] >= 11000:
            catchment_surface = "gt_11000"
        elif self.catalog["total_catchment_surface"] >= 9000:
            catchment_surface = "gt_9000"
        else:
            catchment_surface = "lt_9000"

        is_pv_sol = "non_pv_sol"
        if self.moulinette.data.get("evalenv_rubrique_30-localisation") == "sol":
            is_pv_sol = "pv_sol"

        existing_surface = "existing_lt_10000"
        if self.catalog["existing_surface"] >= 10000:
            existing_surface = "existing_gte_10000"

        return existing_surface, catchment_surface, final_surface, is_pv_sol


class OtherCriteria(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Loi sur l'eau > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible
