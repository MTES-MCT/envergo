from functools import cached_property

from django.contrib.gis.db.models import MultiPolygonField, Union
from django.contrib.gis.measure import Distance as D
from django.db.models import F
from django.db.models.functions import Cast

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation


class N2000100m2(MoulinetteCriterion):
    slug = "n2000_zh_100m2"
    title = "Impact sur zone humide Natura 2000"
    subtitle = "Seuil de déclaration : 100m²"
    header = "Rubrique 3.3.1.0. de la <a target='_blank' rel='noopener' href='https://www.driee.ile-de-france.developpement-durable.gouv.fr/IMG/pdf/nouvelle_nomenclature_tableau_detaille_complete_diffusable-2.pdf'>nomenclature IOTA</a>"  # noqa


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

        if self.catalog["created_surface"] >= 100:
            project_size = "big"
        else:
            project_size = "small"

        return wetland_status, project_size

    @property
    def result_code(self):
        """Return the unique result code"""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
            ("inside", "big"): "soumis",
            ("inside", "small"): "non_soumis",
            ("close_to", "big"): "action_requise_close_to",
            ("close_to", "small"): "non_soumis",
            ("inside_potential", "big"): "action_requise_inside_potential",
            ("inside_potential", "small"): "non_soumis",
            ("outside", "big"): "non_soumis",
            ("outside", "small"): "non_soumis",
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
            "soumis": RESULTS.soumis,
            "non_soumis": RESULTS.non_soumis,
            "non_applicable": RESULTS.non_applicable,
            "action_requise_close_to": RESULTS.action_requise,
            "action_requise_inside_potential": RESULTS.action_requise,
        }
        result = result_matrix[code]
        return result

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


class Natura2000(MoulinetteRegulation):
    slug = "natura2000"
    title = "Natura 2000"
    criterion_classes = [N2000100m2]
