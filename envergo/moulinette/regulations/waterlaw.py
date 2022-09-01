from functools import cached_property

from django.contrib.gis.db.models import MultiPolygonField, Union
from django.db.models import F
from django.db.models.functions import Cast

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import (
    CriterionMap,
    MoulinetteCriterion,
    MoulinetteRegulation,
)


class WaterLaw3310(MoulinetteCriterion):
    slug = "zone_humide"
    choice_label = "Loi sur l'eau > Zone humide"
    title = "Impact sur une zone humide"
    subtitle = "Seuil de déclaration : 1 000 m²"
    header = "Rubrique 3.3.1.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    def get_catalog_data(self):
        data = {}
        data["wetlands_within_25m"] = bool(self.catalog["wetlands_25"])
        data["wetlands_within_100m"] = bool(self.catalog["wetlands_100"])
        data["within_potential_wetlands"] = bool(self.catalog["potential_wetlands"])

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
        elif self.catalog["within_potential_wetlands"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        if self.catalog["project_surface"] >= 1000:
            project_size = "big"
        elif self.catalog["project_surface"] >= 700:
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
            "non_applicable": RESULTS.non_applicable,
            "action_requise_inside": RESULTS.action_requise,
            "action_requise_close_to": RESULTS.action_requise,
            "action_requise_inside_potential": RESULTS.action_requise,
        }
        result = result_matrix[code]
        return result

    @property
    def result_code(self):
        """Return the unique result code"""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
            ("inside", "big"): "soumis",
            ("inside", "medium"): "action_requise_inside",
            ("inside", "small"): "non_soumis",
            ("close_to", "big"): "action_requise_close_to",
            ("close_to", "medium"): "non_soumis",
            ("close_to", "small"): "non_soumis",
            ("inside_potential", "big"): "action_requise_inside_potential",
            ("inside_potential", "medium"): "non_soumis",
            ("inside_potential", "small"): "non_soumis",
            ("outside", "big"): "non_applicable",
            ("outside", "medium"): "non_applicable",
            ("outside", "small"): "non_soumis",
        }
        code = code_matrix[(wetland_status, project_size)]
        return code

    def _get_map(self):

        inside_qs = self.catalog["wetlands_25"].filter(map__display_for_user=True)
        close_qs = self.catalog["wetlands_100"].filter(map__display_for_user=True)
        potential_qs = self.catalog["potential_wetlands"].filter(
            map__display_for_user=True
        )
        polygons = None

        if inside_qs:
            caption = "Le projet se situe dans une zone humide référencée."
            geometries = inside_qs.annotate(geom=Cast("geometry", MultiPolygonField()))
            polygons = [
                {
                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[
                        "polygon"
                    ],
                    "color": "blue",
                    "label": "Zone humide",
                }
            ]
            maps = set([zone.map for zone in inside_qs.select_related("map")])

        elif close_qs and not potential_qs:
            caption = "Le projet se situe à proximité d'une zone humide référencée."
            geometries = close_qs.annotate(geom=Cast("geometry", MultiPolygonField()))
            polygons = [
                {
                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[
                        "polygon"
                    ],
                    "color": "blue",
                    "label": "Zone humide",
                }
            ]
            maps = set([zone.map for zone in close_qs.select_related("map")])

        elif close_qs and potential_qs:
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
            geometries = close_qs.annotate(geom=Cast("geometry", MultiPolygonField()))
            wetlands_polygon = geometries.aggregate(polygon=Union(F("geom")))["polygon"]

            geometries = potential_qs.annotate(
                geom=Cast("geometry", MultiPolygonField())
            )
            potentials_polygon = geometries.aggregate(polygon=Union(F("geom")))[
                "polygon"
            ]

            polygons = [
                {"polygon": wetlands_polygon, "color": "blue", "label": "Zone humide"},
                {
                    "polygon": potentials_polygon,
                    "color": "lightblue",
                    "label": "ZH potentielle",
                },
            ]
            wetlands_maps = [zone.map for zone in close_qs.select_related("map")]
            potential_maps = [zone.map for zone in potential_qs.select_related("map")]
            maps = set(wetlands_maps + potential_maps)

        elif potential_qs:
            caption = "Le projet se situe dans une zone humide potentielle."
            geometries = potential_qs.annotate(
                geom=Cast("geometry", MultiPolygonField())
            )
            polygons = [
                {
                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[
                        "polygon"
                    ],
                    "color": "dodgerblue",
                    "label": "Zone humide potentielle",
                }
            ]
            maps = set([zone.map for zone in potential_qs.select_related("map")])

        if polygons:
            criterion_map = CriterionMap(
                center=self.catalog["coords"],
                polygons=polygons,
                caption=caption,
                sources=maps,
            )
        else:
            criterion_map = None

        return criterion_map


class WaterLaw3220(MoulinetteCriterion):
    slug = "zone_inondable"
    choice_label = "Loi sur l'eau > Zone inondable"
    title = "Impact sur une zone inondable"
    subtitle = "Seuil de déclaration : 400 m²"
    header = "Rubrique 3.2.2.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    def get_catalog_data(self):
        data = {}
        data["flood_zones_within_12m"] = bool(self.catalog["flood_zones_12"])
        return data

    @cached_property
    def result_code(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        else:
            flood_zone_status = "outside"

        if self.catalog["project_surface"] >= 400:
            project_size = "big"
        elif self.catalog["project_surface"] >= 300:
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
                "big": RESULTS.non_applicable,
                "medium": RESULTS.non_applicable,
                "small": RESULTS.non_soumis,
            },
        }

        result = result_matrix[flood_zone_status][project_size]
        return result

    def _get_map(self):
        zone_qs = self.catalog["flood_zones_12"].filter(map__display_for_user=True)
        polygons = None

        if zone_qs:
            caption = "Le projet se situe dans une zone inondable."
            geometries = zone_qs.annotate(geom=Cast("geometry", MultiPolygonField()))
            polygons = [
                {
                    "polygon": [
                        geometries.aggregate(polygon=Union(F("geom")))["polygon"]
                    ][0],
                    "color": "red",
                    "label": "Zone inondable",
                }
            ]
            maps = set([zone.map for zone in zone_qs.select_related("map")])

        if polygons:
            criterion_map = CriterionMap(
                center=self.catalog["coords"],
                polygons=polygons,
                caption=caption,
                sources=maps,
            )
        else:
            criterion_map = None

        return criterion_map


class WaterLaw2150(MoulinetteCriterion):
    slug = "ruissellement"
    choice_label = "Loi sur l'eau > Ruissellement"
    title = "Impact sur l'écoulement des eaux pluviales"
    subtitle = "Seuil de déclaration : 1 ha"
    header = "Rubrique 2.1.5.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa

    @cached_property
    def result_code(self):

        if self.catalog["project_surface"] >= 10000:
            res = RESULTS.soumis
        elif self.catalog["project_surface"] >= 8000:
            res = RESULTS.action_requise
        else:
            res = RESULTS.non_soumis

        return res


class WaterLaw(MoulinetteRegulation):
    slug = "loi_sur_leau"
    title = "Loi sur l'eau"
    criterion_classes = [WaterLaw3310, WaterLaw3220, WaterLaw2150]
