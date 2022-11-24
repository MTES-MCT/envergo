[1mdiff --git a/envergo/moulinette/regulations/loisurleau.py b/envergo/moulinette/regulations/loisurleau.py[m
[1mindex ff1bdf1..6ae7831 100644[m
[1m--- a/envergo/moulinette/regulations/loisurleau.py[m
[1m+++ b/envergo/moulinette/regulations/loisurleau.py[m
[36m@@ -1,9 +1,6 @@[m
 from functools import cached_property[m
 [m
[31m-from django.contrib.gis.db.models import MultiPolygonField, Union[m
 from django.contrib.gis.geos import GEOSGeometry[m
[31m-from django.db.models import F[m
[31m-from django.db.models.functions import Cast[m
 [m
 from envergo.evaluations.models import RESULTS[m
 from envergo.moulinette.regulations import ([m
[36m@@ -98,52 +95,59 @@[m [mclass ZoneHumide(MoulinetteCriterion):[m
         return code[m
 [m
     def _get_map(self):[m
[31m-        inside_qs = self.catalog["wetlands_25"].filter(map__display_for_user=True)[m
[31m-        close_qs = self.catalog["wetlands_100"].filter(map__display_for_user=True)[m
[31m-        potential_qs = self.catalog["potential_wetlands"].filter([m
[31m-            map__display_for_user=True[m
[31m-        )[m
[32m+[m[32m        inside_qs = [[m
[32m+[m[32m            zone for zone in self.catalog["wetlands_25"] if zone.map.display_for_user[m
[32m+[m[32m        ][m
[32m+[m[32m        close_qs = [[m
[32m+[m[32m            zone for zone in self.catalog["wetlands_100"] if zone.map.display_for_user[m
[32m+[m[32m        ][m
[32m+[m[32m        potential_qs = [[m
[32m+[m[32m            zone[m
[32m+[m[32m            for zone in self.catalog["potential_wetlands"][m
[32m+[m[32m            if zone.map.display_for_user[m
[32m+[m[32m        ][m
         polygons = None[m
 [m
         if inside_qs:[m
             caption = "Le projet se situe dans une zone humide référencée."[m
[31m-            geometries = inside_qs.annotate(geom=Cast("geometry", MultiPolygonField()))[m
[32m+[m[32m            polygon = GEOSGeometry("POLYGON EMPTY", srid=3857)[m
[32m+[m[32m            for zone in inside_qs:[m
[32m+[m[32m                polygon = polygon.union(zone.geom)[m
[32m+[m
             polygons = [[m
                 {[m
[31m-                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[[m
[31m-                        "polygon"[m
[31m-                    ],[m
[32m+[m[32m                    "polygon": polygon,[m
                     "color": BLUE,[m
                     "label": "Zone humide",[m
                 }[m
             ][m
[31m-            maps = set([zone.map for zone in inside_qs[7m.select_related("map")[27m])[m
[32m+[m[32m            maps = set([zone.map for zone in inside_qs[7m[27m])[m
 [m
         elif close_qs and not potential_qs:[m
             caption = "Le projet se situe à proximité d'une zone humide référencée."[m
[31m-            geometries = close_qs.annotate(geom=Cast("geometry", MultiPolygonField()))[m
[32m+[m[32m            polygon = GEOSGeometry("POLYGON EMPTY")[m
[32m+[m[32m            for zone in close_qs:[m
[32m+[m[32m                polygon = polygon.union(zone.geom)[m
[32m+[m
             polygons = [[m
                 {[m
[31m-                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[[m
[31m-                        "polygon"[m
[31m-                    ],[m
[32m+[m[32m                    "polygon": polygon,[m
                     "color": BLUE,[m
                     "label": "Zone humide",[m
                 }[m
             ][m
[31m-            maps = set([zone.map for zone in close_qs[7m.select_related("map")[27m])[m
[32m+[m[32m            maps = set([zone.map for zone in close_qs[7m[27m])[m
 [m
         elif close_qs and potential_qs:[m
             caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."[m
[31m-            geometries = close_qs.annotate(geom=Cast("geometry", MultiPolygonField()))[m
[31m-            wetlands_polygon = geometries.aggregate(polygon=Union(F("geom")))["polygon"][m
 [m
[31m-            geometries = potential_qs.annotate([m
[31m-                geom=Cast("geometry", MultiPolygonField())[m
[31m-            )[m
[31m-            potentials_polygon = geometries.aggregate(polygon=Union(F("geom")))[[m
[31m-                "polygon"[m
[31m-            ][m
[32m+[m[32m            wetlands_polygon = GEOSGeometry("POLYGON EMPTY", srid=3857)[m
[32m+[m[32m            for zone in close_qs:[m
[32m+[m[32m                wetlands_polygon = wetlands_polygon.union(zone.geom)[m
[32m+[m
[32m+[m[32m            potentials_polygon = GEOSGeometry("POLYGON EMPTY", srid=3857)[m
[32m+[m[32m            for zone in potential_qs:[m
[32m+[m[32m                potentials_polygon = potentials_polygon.union(zone.geom)[m
 [m
             polygons = [[m
                 {"polygon": wetlands_polygon, "color": BLUE, "label": "Zone humide"},[m
[36m@@ -153,25 +157,24 @@[m [mclass ZoneHumide(MoulinetteCriterion):[m
                     "label": "Zone humide potentielle",[m
                 },[m
             ][m
[31m-            wetlands_maps = [zone.map for zone in close_qs[7m.select_related("map")[27m][m
[31m-            potential_maps = [zone.map for zone in potential_qs[7m.select_related("map")[27m][m
[32m+[m[32m            wetlands_maps = [zone.map for zone in close_qs[7m[27m][m
[32m+[m[32m            potential_maps = [zone.map for zone in potential_qs[7m[27m][m
             maps = set(wetlands_maps + potential_maps)[m
 [m
         elif potential_qs:[m
             caption = "Le projet se situe dans une zone humide potentielle."[m
[31m-            geometries = potential_qs.annotate([m
[31m-                geom=Cast("geometry", MultiPolygonField())[m
[31m-            )[m
[32m+[m[32m            potentials_polygon = GEOSGeometry("POLYGON EMPTY", srid=3857)[m
[32m+[m[32m            for zone in potential_qs:[m
[32m+[m[32m                potentials_polygon = potentials_polygon.union(zone.geom)[m
[32m+[m
             polygons = [[m
                 {[m
[31m-                    "polygon": geometries.aggregate(polygon=Union(F("geom")))[[m
[31m-                        "polygon"[m
[31m-                    ],[m
[32m+[m[32m                    "polygon": potentials_polygon,[m
                     "color": LIGHTBLUE,[m
                     "label": "Zone humide potentielle",[m
                 }[m
             ][m
[31m-            maps = set([zone.map for zone in potential_qs[7m.select_related("map")[27m])[m
[32m+[m[32m            maps = set([zone.map for zone in potential_qs[7m[27m])[m
 [m
         if polygons:[m
             criterion_map = Map([m
[36m@@ -231,15 +234,16 @@[m [mclass ZoneInondable(MoulinetteCriterion):[m
         return result[m
 [m
     def _get_map(self):[m
[31m-        zone_qs = self.catalog["flood_zones_12"] #.filter(map__display_for_user=True)[m
         polygons = None[m
[31m-        polygon = GEOSGeometry('POLYGON EMPTY')[m
[32m+[m[32m        zone_qs = [[m
[32m+[m[32m            zone for zone in self.catalog["flood_zones_12"] if zone.map.display_for_user[m
[32m+[m[32m        ][m
[32m+[m[32m        polygon = GEOSGeometry("POLYGON EMPTY", srid=3857)[m
         for zone in zone_qs:[m
             polygon = polygon.union(zone.geom)[m
 [m
         if zone_qs:[m
             caption = "Le projet se situe dans une zone inondable."[m
[31m-            # geometries = zone_qs.annotate(geom=Cast("geometry", MultiPolygonField()))[m
             polygons = [[m
                 {[m
                     "polygon": polygon,[m
[1mdiff --git a/envergo/moulinette/views.py b/envergo/moulinette/views.py[m
[1mindex 9709eef..8e2c812 100644[m
[1m--- a/envergo/moulinette/views.py[m
[1m+++ b/envergo/moulinette/views.py[m
[36m@@ -83,6 +83,8 @@[m [mclass MoulinetteMixin:[m
         context["feedback_form"] = FeedbackForm()[m
         context["display_feedback_form"] = not self.request.GET.get("feedback", False)[m
 [m
[32m+[m[32m        # json = moulinette.loi_sur_leau.zone_inondable._get_map().to_json()[m
[32m+[m
         return context[m
 [m
     def render_to_response(self, context, **response_kwargs):[m
