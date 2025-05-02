from types import SimpleNamespace

from django import forms
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import Intersection, Length
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance
from django.db import connection
from django.db.models import Sum
from django.db.models.functions import Cast

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Line
from envergo.geodata.utils import EPSG_WGS84, get_best_epsg_for_location
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon


class EspecesProtegees(CriterionEvaluator):
    """Legacy criterion for protected species."""

    choice_label = "EP > EP (obsolète)"
    slug = "ep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog

    def get_result_data(self):
        return "soumis"


class EspecesProtegeesSimple(EspecesProtegees):
    """Basic criterion: always returns "soumis."""

    choice_label = "EP > EP simple"
    slug = "ep_simple"


class EspecesProtegeesSettings(forms.Form):
    replantation_coefficient = forms.DecimalField(
        label="Coefficient de replantation",
        help_text="Coefficient « R » de replantation des haies",
        min_value=0,
        max_value=10,
        max_digits=4,
        decimal_places=1,
    )


class EspecesProtegeesAisne(CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Aisne"
    slug = "ep_aisne"
    settings_form_class = EspecesProtegeesSettings

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


class Densite(CriterionEvaluator):
    """Legacy criterion for protected species."""

    choice_label = "EP > Densité"
    slug = "densite"

    CODE_MATRIX = {
        "non_applicable": "non_applicable",
    }

    @classmethod
    def get_truncated_circle(cls, circle_geom, map_name):
        """find the intersection of a circle with a map zones

        Django ORM does not support cumulative intersection (reduce(ST_Intersection)) across multiple geometries
        so it uses raw SQL
        Returns:
            - the intersection of the circle with the map zones
            - None if there is no intersection
        """

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ST_AsText(
                    ST_Intersection(
                        ST_GeomFromEWKT(%s),
                        ST_Union(z.geometry::geometry)
                    )
                )
                FROM geodata_zone z
                INNER JOIN geodata_map m ON z.map_id = m.id
                WHERE m.name = %s
                  AND ST_Intersects(z.geometry, ST_GeomFromEWKT(%s))
            """,
                [circle_geom.ewkt, map_name, circle_geom.ewkt],
            )
            wkt = cursor.fetchone()[0]
            if wkt:
                geom = GEOSGeometry(wkt)
                geom.srid = circle_geom.srid  # Set SRID explicitly
            else:
                geom = None
            return geom

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if not haies:
            return catalog

        # get two circles at 200m and 5000m from the centroid of the hedges to remove
        centroid_shapely = haies.get_centroid_to_remove()
        centroid_geos = GEOSGeometry(centroid_shapely.wkt, srid=EPSG_WGS84)

        # use specific projection to be able to use meters for buffering
        epsg_utm = get_best_epsg_for_location(centroid_geos.x, centroid_geos.y)
        centroid_meter = centroid_geos.transform(epsg_utm, clone=True)
        circle_200 = centroid_meter.buffer(200)
        circle_5000 = centroid_meter.buffer(5000)

        circle_200 = circle_200.transform(
            EPSG_WGS84, clone=True
        )  # switch back to WGS84
        circle_5000 = circle_5000.transform(EPSG_WGS84, clone=True)

        # remove the sea from the circles
        truncated_circle_200 = self.get_truncated_circle(
            circle_200, "Calvados buffer 5km sans la mer"
        )  # TODO this map should depend on the department
        truncated_circle_5000 = self.get_truncated_circle(
            circle_5000, "Calvados buffer 5km sans la mer"
        )  # TODO this map should depend on the department

        if truncated_circle_200 and truncated_circle_5000:
            # get the area of the circles
            truncated_circle_200_m = truncated_circle_200.transform(
                epsg_utm, clone=True
            )  # use specific projection to compute the area in square meters
            truncated_circle_5000_m = truncated_circle_5000.transform(
                epsg_utm, clone=True
            )

            area_200 = truncated_circle_200_m.area
            area_5000 = truncated_circle_5000_m.area

            # get the hedges in the circles : FOR DISPLAY ONLY => it can be removed if there is performance issues
            # hedges_5000 = Line.objects.filter(
            #     map__name="haies_2024_dpt14_buffer5km",
            #     geometry__intersects=truncated_circle_5000,
            # ).select_related("map")

            # get the length of the hedges in the circles
            length_200 = (
                Line.objects.filter(
                    geometry__intersects=truncated_circle_200,
                    map__name="haies_2024_dpt14_buffer5km",
                )  # TODO this map should depend on the department
                .annotate(clipped=Intersection("geometry", truncated_circle_200))
                .annotate(length=Length(Cast("clipped", GeometryField())))
                .aggregate(total=Sum("length"))["total"]
            )
            length_200 = length_200 if length_200 else Distance(0)
            length_5000 = (
                Line.objects.filter(
                    geometry__intersects=truncated_circle_5000,
                    map__name="haies_2024_dpt14_buffer5km",
                )  # TODO this map should depend on the department
                .annotate(clipped=Intersection("geometry", truncated_circle_5000))
                .annotate(length=Length(Cast("clipped", GeometryField())))
                .aggregate(total=Sum("length"))["total"]
            )
            length_5000 = length_5000 if length_5000 else Distance(0)

            polygons = [
                MapPolygon(
                    [SimpleNamespace(geometry=truncated_circle_200)],
                    "orange",
                    "200m",
                ),
                MapPolygon(
                    [SimpleNamespace(geometry=truncated_circle_5000)],
                    "blue",
                    "5km",
                ),
                # MapPolygon(
                #     hedges_5000,
                #     "green",
                #     "Haies existantes",
                # ),
                MapPolygon(
                    [
                        SimpleNamespace(
                            geometry=GEOSGeometry(hedge.geometry.wkt, srid=EPSG_WGS84)
                        )
                        for hedge in haies.hedges_to_remove()
                    ],
                    "red",
                    "Haies à détruire",
                    class_name="hedge to-remove",
                ),
            ]

            map = Map(
                type="regulation",
                center=centroid_geos,
                entries=polygons,
                truncate=False,
                display_marker_at_center=True,
                zoom=None,
                ratio_classes="ratio-2x1 ratio-sm-4x5",
                fixed=False,
            )

            catalog["map"] = map
            catalog["area_200"] = area_200
            catalog["area_5000"] = area_5000
            catalog["length_200"] = length_200
            catalog["length_5000"] = length_5000
            catalog["density_200"] = (
                length_200.standard / area_200 if area_200 > 0 else 1000
            )
            catalog["density_5000"] = (
                length_5000.standard / area_5000 if area_5000 > 0 else 1000
            )

        return catalog

    def get_result_data(self):
        return "non_applicable"
