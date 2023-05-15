from functools import cached_property

from django.contrib.gis.measure import Distance as D

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import (
    Map,
    MapPolygon,
    MoulinetteCriterion,
    MoulinetteRegulation,
    RequiredAction,
    Stake,
)

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"


class ZoneHumide(MoulinetteCriterion):
    slug = "zone_humide"
    choice_label = "Loi sur l'eau > Zone humide"
    title = "Impact sur une zone humide"
    subtitle = "Seuil de déclaration : 1 000 m²"
    header = "Rubrique 3.3.1.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    CODES = [
        "soumis",
        "non_soumis",
        "non_concerne",
        "action_requise",
        "action_requise_proche",
        "action_requise_dans_doute",
    ]

    def get_catalog_data(self):
        data = {}

        if "wetlands_25" not in data:
            data["wetlands_25"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=25)
            ]
            data["wetlands_within_25m"] = bool(data["wetlands_25"])

        if "wetlands_100" not in data:
            data["wetlands_100"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=100)
            ]
            data["wetlands_within_100m"] = bool(data["wetlands_100"])

        if "potential_wetlands_0" not in data:
            data["potential_wetlands_0"] = [
                zone for zone in self.catalog["potential_wetlands"] if zone.distance <= D(m=0)
            ]
            data["potential_wetlands_within_0m"] = bool(data["potential_wetlands_0"])

        return data

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

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "soumis": RESULTS.soumis,
            "non_soumis": RESULTS.non_soumis,
            "non_concerne": RESULTS.non_concerne,
            "action_requise": RESULTS.action_requise,
            "action_requise_proche": RESULTS.action_requise,
            "action_requise_dans_doute": RESULTS.action_requise,
        }
        result = result_matrix[code]
        return result

    @property
    def result_code(self):
        """Return the unique result code"""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
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
        code = code_matrix[(wetland_status, project_size)]
        return code

    def _get_map(self):
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
            caption = "Le projet ne se situe pas dans zone humide référencée."

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

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.SOUMIS,
                text="n'impacte pas plus de 1 000 m² de zone humide",
            )
        return action


class ZoneInondable(MoulinetteCriterion):
    slug = "zone_inondable"
    choice_label = "Loi sur l'eau > Zone inondable"
    title = "Impact sur une zone inondable"
    subtitle = "Seuil de déclaration : 400 m²"
    header = "Rubrique 3.2.2.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    def get_catalog_data(self):
        data = {}

        if 'flood_zones_12' not in self.catalog:
            data["flood_zones_12"] = [
                zone for zone in self.catalog['flood_zones'] if zone.distance <= D(m=12)
            ]
            data["flood_zones_within_12m"] = bool(data["flood_zones_12"])
        return data

    @cached_property
    def result_code(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        else:
            flood_zone_status = "outside"

        if self.catalog["final_surface"] >= 400:
            project_size = "big"
        elif self.catalog["final_surface"] >= 300:
            project_size = "medium"
        else:
            project_size = "small"

        result_matrix = {
            "inside": {
                "big": RESULTS.soumis,
                "medium": RESULTS.action_requise,
                "small": RESULTS.non_soumis,
            },
            "outside": {
                "big": RESULTS.non_concerne,
                "medium": RESULTS.non_concerne,
                "small": RESULTS.non_soumis,
            },
        }

        result = result_matrix[flood_zone_status][project_size]
        return result

    def _get_map(self):
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

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.SOUMIS,
                text="n'impacte pas plus de 400m² de zone inondable",
            )
        return action


class Ruissellement(MoulinetteCriterion):
    slug = "ruissellement"
    choice_label = "Loi sur l'eau > Ruissellement"
    title = "Impact sur l'écoulement des eaux pluviales"
    subtitle = "Seuil de déclaration : 1 ha"
    header = "Rubrique 2.1.5.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    CODES = ["soumis", "action_requise", "non_soumis"]

    @cached_property
    def result_code(self):

        if self.catalog["final_surface"] >= 10000:
            res = RESULTS.soumis
        elif self.catalog["final_surface"] >= 8000:
            res = RESULTS.action_requise
        else:
            res = RESULTS.non_soumis

        return res

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.SOUMIS,
                text="a une surface totale, augmentée de l'aire d'écoulement d'eaux de "
                "pluie interceptée, inférieure à 1 ha",
            )
        return action


class OtherCriteria(MoulinetteCriterion):
    slug = "autres_rubriques"
    choice_label = "Loi sur l'eau > Autres rubriques"
    title = "Autres rubriques"

    CODES = ["non_disponible"]

    @cached_property
    def result_code(self):
        return RESULTS.non_disponible


class ZoneHumideVieJaunay85(MoulinetteCriterion):
    slug = "zone_humide_vie_jaunay_85"
    choice_label = "Loi sur l'eau > 85 - Zone humide Vie & Jaunay"
    title = "Impact sur une zone humide (SAGE Vie et Jaunay)"
    subtitle = "Seuil d'interdiction : 1 000 m²"
    header = "Article 5 du <a target='_blank' rel='noopener' href='https://www.gesteau.fr/document/reglement-du-sage-de-la-vie-et-du-jaunay'>règlement du SAGE Vie et Jaunay</a>"  # noqa

    CODES = [
        "interdit",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "non_soumis",
        "non_concerne",
    ]

    def get_catalog_data(self):
        data = {}
        wetlands = self.catalog["forbidden_wetlands"]

        if "forbidden_wetlands_25" not in data:
            data["forbidden_wetlands_25"] = [
                zone for zone in wetlands if zone.distance <= D(m=25)
            ]

        if "forbidden_wetlands_100" not in data:
            data["forbidden_wetlands_100"] = [
                zone for zone in wetlands if zone.distance <= D(m=100)
            ]
            data["forbidden_wetlands_within_100m"] = bool(
                data["forbidden_wetlands_100"]
            )

        return data

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["forbidden_wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["forbidden_wetlands_within_100m"]:
            wetland_status = "close_to"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= 1000:
            project_size = "big"
        elif self.catalog["created_surface"] >= 700:
            project_size = "medium"
        else:
            project_size = "small"

        return wetland_status, project_size

    @property
    def result_code(self):
        """Return the unique result code."""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
            ("inside", "big"): "interdit",
            ("inside", "medium"): "action_requise_interdit",
            ("inside", "small"): "non_soumis",
            ("close_to", "big"): "action_requise_proche_interdit",
            ("close_to", "medium"): "non_soumis",
            ("close_to", "small"): "non_soumis",
            ("outside", "big"): "non_concerne",
            ("outside", "medium"): "non_concerne",
            ("outside", "small"): "non_concerne",
        }
        code = code_matrix[(wetland_status, project_size)]
        return code

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "interdit": RESULTS.interdit,
            "action_requise_interdit": RESULTS.action_requise,
            "action_requise_proche_interdit": RESULTS.action_requise,
            "non_soumis": RESULTS.non_soumis,
            "non_concerne": RESULTS.non_concerne,
        }
        result = result_matrix[code]
        return result

    def _get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLACK, "Zone humide"))

        if self.catalog["forbidden_wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif self.catalog["forbidden_wetlands_within_100m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."
        else:
            caption = "Le projet ne se situe pas dans zone humide référencée."

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

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.INTERDIT,
                text="n’impacte pas plus 1 000 m² de zone humide référencée dans le règlement du SAGE Vie et Jaunay",
            )
        return action


class LoiSurLEau(MoulinetteRegulation):
    slug = "loi_sur_leau"
    title = "Loi sur l'eau"
    criterion_classes = [
        ZoneHumide,
        ZoneHumideVieJaunay85,
        ZoneInondable,
        Ruissellement,
        OtherCriteria,
    ]

    @cached_property
    def result(self):
        """Compute global result from individual criterions."""

        results = [criterion.result for criterion in self.criterions]

        if RESULTS.interdit in results:
            result = RESULTS.interdit
        elif RESULTS.soumis in results:
            result = RESULTS.soumis
        elif RESULTS.action_requise in results:
            result = RESULTS.action_requise
        elif RESULTS.a_verifier in results:
            result = RESULTS.iota_a_verifier
        else:
            result = RESULTS.non_soumis

        return result
