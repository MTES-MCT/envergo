from envergo.evaluations.models import RESULTS
from envergo.geodata.utils import get_catchment_area
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon
from envergo.moulinette.regulations.mixins import ZoneHumideMixin, ZoneInondableMixin

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"
PINK = "#FF9575"


class ZoneHumide(ZoneHumideMixin, CriterionEvaluator):
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

        wetlands_qs = [
            zone for zone in self.catalog["wetlands"] if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLUE, "Zone humide"))

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

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
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class ZoneInondable(ZoneInondableMixin, CriterionEvaluator):
    choice_label = "Loi sur l'eau > Zone inondable"
    slug = "zone_inondable"

    CODES = ["soumis", "action_requise", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        ("inside", "big"): "soumis",
        ("inside", "medium"): "action_requise",
        ("inside", "small"): "non_soumis",
        ("inside_potential", "big"): "action_requise_dans_doute",
        ("inside_potential", "medium"): "non_soumis",
        ("inside_potential", "small"): "non_soumis",
        ("outside", "big"): "non_concerne",
        ("outside", "medium"): "non_concerne",
        ("outside", "small"): "non_concerne",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_soumis": RESULTS.non_soumis,
        "non_concerne": RESULTS.non_concerne,
        "action_requise": RESULTS.action_requise,
        "action_requise_dans_doute": RESULTS.action_requise,
    }

    def get_result_data(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        elif self.catalog["potential_flood_zones_within_0m"]:
            flood_zone_status = "inside_potential"
        else:
            flood_zone_status = "outside"

        if self.catalog["final_surface"] >= 400:
            project_size = "big"
        elif self.catalog["final_surface"] >= 300:
            project_size = "medium"
        else:
            project_size = "small"

        return flood_zone_status, project_size

    def get_map(self):
        map_polygons = []

        zone_qs = [
            zone for zone in self.catalog["flood_zones"] if zone.map.display_for_user
        ]
        if zone_qs:
            map_polygons.append(MapPolygon(zone_qs, "red", "Zone inondable"))

        potential_qs = [
            zone
            for zone in self.catalog["potential_flood_zones"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, PINK, "Zone inondable potentielle")
            )

        if self.catalog["flood_zones_within_12m"]:
            caption = "Le projet se situe dans une zone inondable."
        elif self.catalog["potential_flood_zones_within_0m"]:
            caption = "Le projet se situe dans une zone inondable potentielle."
        else:
            caption = "Le projet ne se situe pas en zone inondable."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class EcoulementSansBV(CriterionEvaluator):
    choice_label = "Loi sur l'eau > Écoulement EP sans BV"
    slug = "ecoulement_sans_bv"

    CODES = ["soumis", "action_requise", "non_soumis"]

    CODE_MATRIX = {
        "big": "soumis",
        "medium": "action_requise",
        "small": "non_soumis",
    }

    def get_result_data(self):
        if self.catalog["final_surface"] >= 10000:
            project_size = "big"
        elif self.catalog["final_surface"] >= 8000:
            project_size = "medium"
        else:
            project_size = "small"

        return project_size


# This was the old evaluator name
# it has to stay here for compatibility reasons
class Ruissellement(EcoulementSansBV):
    choice_label = "Loi sur l'eau > Ruissellement (obsolète)"


class EcoulementAvecBV(CriterionEvaluator):
    choice_label = "Loi sur l'eau > Écoulement EP avec BV"
    slug = "ecoulement_avec_bv"

    CODES = ["soumis", "action_requise_probable_1ha", "action_requise", "non_soumis"]

    CODE_MATRIX = {
        ("gt_11000", "gt_1ha"): "soumis",
        ("gt_11000", "gt_7000"): "action_requise_probable_1ha",
        ("gt_11000", "gt_500"): "action_requise",
        ("gt_11000", "lt_100"): "non_soumis",
        ("gt_9000", "gt_1ha"): "soumis",
        ("gt_9000", "gt_7000"): "action_requise",
        ("gt_9000", "gt_500"): "action_requise",
        ("gt_9000", "lt_100"): "non_soumis",
        ("lt_9000", "gt_1ha"): "soumis",
        ("lt_9000", "gt_7000"): "non_soumis",
        ("lt_9000", "gt_500"): "non_soumis",
        ("lt_9000", "lt_100"): "non_soumis",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "action_requise_probable_1ha": RESULTS.action_requise,
        "action_requise": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
    }

    def get_catalog_data(self):
        data = {}

        # If we cannot compute the catchment area surface, we have to consider
        # the value is 0
        surface = get_catchment_area(self.catalog["lng"], self.catalog["lat"]) or 0
        total_surface = surface + self.catalog["final_surface"]

        data["catchment_surface"] = surface
        data["total_catchment_surface"] = total_surface
        return data

    def get_result_data(self):
        if self.catalog["final_surface"] >= 10000:
            final_surface = "gt_1ha"
        elif self.catalog["final_surface"] >= 7000:
            final_surface = "gt_7000"
        elif self.catalog["final_surface"] >= 500:
            final_surface = "gt_500"
        else:
            final_surface = "lt_500"

        if self.catalog["total_catchment_surface"] >= 11000:
            catchment_surface = "gt_11000"
        elif self.catalog["total_catchment_surface"] >= 9000:
            catchment_surface = "gt_9000"
        else:
            catchment_surface = "lt_9000"

        return catchment_surface, final_surface


class OtherCriteria(CriterionEvaluator):
    choice_label = "Loi sur l'eau > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible
