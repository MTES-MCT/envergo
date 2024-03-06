from django.contrib.gis.measure import Distance as D

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon
from envergo.moulinette.regulations.mixins import ZoneHumideMixin

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"


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
        elif self.catalog["potential_wetlands_within_0m"]:
            wetland_status = "inside_potential"
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
            and not self.catalog["potential_wetlands_within_0m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and self.catalog["potential_wetlands_within_0m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_0m"] and potential_qs:
            caption = "Le projet se situe dans une zone humide potentielle."
        else:
            caption = "Le projet ne se situe pas dans une zone humide référencée."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
                zoom=18,
            )
        else:
            criterion_map = None

        return criterion_map


class ZoneInondable(CriterionEvaluator):
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

    def get_catalog_data(self):
        data = super().get_catalog_data()

        if "flood_zones_12" not in self.catalog:
            data["flood_zones_12"] = [
                zone for zone in self.catalog["flood_zones"] if zone.distance <= D(m=12)
            ]
            data["flood_zones_within_12m"] = bool(data["flood_zones_12"])

        if "potential_flood_zones_0" not in self.catalog:
            data["potential_flood_zones_0"] = [
                zone
                for zone in self.catalog["potential_flood_zones"]
                if zone.distance <= D(m=0)
            ]
            data["potential_flood_zones_within_0m"] = bool(
                data["potential_flood_zones_0"]
            )

        return data

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
        zone_qs = [
            zone for zone in self.catalog["flood_zones"] if zone.map.display_for_user
        ]

        if zone_qs:
            if self.catalog["flood_zones_within_12m"]:
                caption = "Le projet se situe dans une zone inondable."
            else:
                caption = "Le projet ne se situe pas en zone inondable."

            map_polygons = [MapPolygon(zone_qs, "red", "Zone inondable")]
            criterion_map = Map(
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
                zoom=18,
            )
        else:
            criterion_map = None

        return criterion_map


class Ruissellement(CriterionEvaluator):
    choice_label = "Loi sur l'eau > Ruissellement"
    slug = "ruissellement"

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


class OtherCriteria(CriterionEvaluator):
    choice_label = "Loi sur l'eau > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible
