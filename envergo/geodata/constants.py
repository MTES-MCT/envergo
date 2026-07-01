"""Coordinate Reference System (CRS) identifiers used across the project.

Single source of truth — import these rather than redeclaring the numbers.
"""

# WGS84 — geographic CRS, lat/lng in degrees. Storage and display CRS for all
# vector data; what Leaflet and GeoJSON expect. Not suitable for metric math.
EPSG_WGS84 = 4326

# Lambert 93 — France's official projected CRS, in meters. CRS of the catchment
# raster and of exports to French administrative systems. Mainland only.
EPSG_LAMB93 = 2154
