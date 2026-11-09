"""List the libraries the running application is made of."""

import json
from dataclasses import dataclass
from importlib.metadata import distributions

from django.conf import settings
from django.contrib.gis.gdal.libgdal import gdal_version
from django.contrib.gis.geos.libgeos import geos_version_tuple
from packaging.utils import canonicalize_name

NPM_LOCKFILE = "package-lock.json"


@dataclass(frozen=True)
class Component:
    """One library at the exact version the application uses."""

    name: str
    version: str
    ecosystem: str  # OSV ecosystem name: "PyPI", "npm" or "OSS-Fuzz".


def read_components():
    """Return every library the application runs on, once each."""
    python_components = read_python_components()
    npm_components = read_npm_components()
    geo_components = read_geo_components()
    components = python_components + npm_components + geo_components
    return sorted(set(components), key=lambda c: (c.ecosystem, c.name))


def read_python_components():
    """Read the packages installed in the current Python environment."""
    return [
        Component(canonicalize_name(distribution.name), distribution.version, "PyPI")
        for distribution in distributions()
    ]


def read_npm_components():
    """Read the lockfile, since `node_modules` is absent from the deployed app.

    Development packages are included because they run during the build.
    """
    lockfile_path = settings.ROOT_DIR / NPM_LOCKFILE
    packages = json.loads(lockfile_path.read_text())["packages"]

    components = []
    for path, package in packages.items():
        if not path:  # The root entry is envergo itself.
            continue
        # A nested install path looks like "node_modules/csso/node_modules/css-tree".
        name = path.rsplit("node_modules/", 1)[1]
        components.append(Component(name, package["version"], "npm"))
    return components


def read_geo_components():
    """Read the geo libraries loaded in this process, as OSV files them.

    OSV has no entry for these C libraries as such. GDAL's flaws are filed under its
    PyPI package, whose versions follow the library, and GEOS's under its OSS-Fuzz project.
    """
    gdal = gdal_version().decode()
    geos = ".".join(str(part) for part in geos_version_tuple())
    return [Component("gdal", gdal, "PyPI"), Component("geos", geos, "OSS-Fuzz")]
