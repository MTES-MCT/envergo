"""Hedge density computations, cached by geometry content.

Values are cached under a geometry-derived key, so identical drawings
share one computation. Density also depends on the imported hedgerow
maps: after an import, cached values may be outdated for up to
DENSITY_CACHE_TIMEOUT.
"""

import hashlib
import json

from django.contrib.gis.geos import GEOSGeometry
from django.core.cache import cache

from envergo.geodata.constants import EPSG_WGS84
from envergo.geodata.utils import (
    compute_hedge_densities_around_point,
    compute_hedge_density_around_lines,
)

# Bump to invalidate all entries after a change in the computation itself.
CACHE_VERSION = "v1"

DENSITY_CACHE_TIMEOUT = 7 * 24 * 3600


def zero_densities(radii) -> dict:
    """The density dict shape for an empty hedge subset."""
    value = {}
    for radius in radii:
        value[f"length_{radius}"] = 0.0
        value[f"area_{radius}_ha"] = 0.0
        value[f"density_{radius}"] = 0.0
    return value


def hedge_set_content_key(hedges) -> str:
    """Digest a hedge subset's geometry, order-insensitive."""
    serialized_geometries = sorted(
        json.dumps(h.latLngs, sort_keys=True, separators=(",", ":")) for h in hedges
    )
    payload = "|".join(serialized_geometries)
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_lines_bundle(hedges, radius):
    """Raw line-buffer density bundle ({"density", "artifacts"}), uncached."""
    hedges_geom = hedges.to_multilinestring()
    return compute_hedge_density_around_lines(hedges_geom, radius)


def compute_centroid_bundles(hedges, radii):
    """Raw centroid-based density bundles keyed by radius, plus the centroid."""
    centroid_geos = GEOSGeometry(hedges.centroid.wkt, srid=EPSG_WGS84)
    bundles = compute_hedge_densities_around_point(centroid_geos, radii=list(radii))
    return bundles, centroid_geos


def lines_cache_key(hedges, radius) -> str:
    digest = hedge_set_content_key(hedges)
    return f"hedge_density:{CACHE_VERSION}:lines:{radius}:{digest}"


def centroid_cache_key(hedges, radii) -> str:
    digest = hedge_set_content_key(hedges)
    radii_part = "-".join(str(r) for r in radii)
    return f"hedge_density:{CACHE_VERSION}:centroid:{radii_part}:{digest}"


def cached_density_around_lines(hedges, radius=400) -> dict:
    """Density in a line buffer around the hedges, cached by geometry."""
    if not hedges:
        return zero_densities([radius])

    key = lines_cache_key(hedges, radius)
    value = cache.get(key)
    if value is None:
        bundle = compute_lines_bundle(hedges, radius)
        value = {
            f"length_{radius}": bundle["artifacts"]["length"],
            f"area_{radius}_ha": bundle["artifacts"]["area_ha"],
            f"density_{radius}": bundle["density"],
        }
        cache.set(key, value, DENSITY_CACHE_TIMEOUT)
    return value


def cached_densities_around_centroid(hedges, radii=(200, 5000)) -> dict:
    """Densities in circles around the hedges' centroid, cached by geometry."""
    if not hedges:
        return zero_densities(radii)

    key = centroid_cache_key(hedges, radii)
    value = cache.get(key)
    if value is None:
        bundles, _ = compute_centroid_bundles(hedges, radii)
        value = {}
        for radius in radii:
            bundle = bundles[radius]
            value[f"length_{radius}"] = bundle["artifacts"]["length"]
            value[f"area_{radius}_ha"] = bundle["artifacts"]["area_ha"]
            value[f"density_{radius}"] = bundle["density"]
        cache.set(key, value, DENSITY_CACHE_TIMEOUT)
    return value
