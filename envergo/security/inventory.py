"""List the libraries the running application is made of."""

import ctypes
import json
import logging
import platform
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import distributions

import fiona
from django.conf import settings
from django.contrib.gis.gdal.libgdal import gdal_version
from django.contrib.gis.geos.libgeos import geos_version_tuple
from packaging.utils import canonicalize_name
from PIL import features
from psycopg import pq

logger = logging.getLogger(__name__)

NPM_LOCKFILE = "package-lock.json"


class Ecosystem(StrEnum):
    """Where OSV files a library's flaws. The values are OSV's own names."""

    PYPI = "PyPI"
    NPM = "npm"
    OSS_FUZZ = "OSS-Fuzz"
    # The name is a repository address, and the version a release tag.
    GIT = "GIT"


@dataclass(frozen=True)
class Component:
    """One library at the exact version the application uses."""

    name: str
    version: str
    ecosystem: Ecosystem


@dataclass(frozen=True)
class RuntimeLibrary:
    """A program or bundled C library that OSV knows by repository and release tag."""

    # Spelled exactly as in OSV's records. OSV compares it character for character.
    repository: str
    # Returns the running version, as "1.2.3", or None when it isn't installed.
    read_version: Callable[[], str | None]
    tag_prefix: str = ""
    tag_separator: str = "."

    def tag(self, version):
        """Return the release tag for a version, in this project's own naming."""
        return self.tag_prefix + version.replace(".", self.tag_separator)


# Programs and C libraries that no package manager lists, so the inventory cannot
# find them on its own. This list is maintained by hand. Each entry reads the
# running version, and OSV matches it by repository and release tag. Pillow
# reports the libraries its wheel bundles.
RUNTIME_LIBRARIES = [
    RuntimeLibrary(
        "https://github.com/python/cpython",
        lambda: platform.python_version(),
        tag_prefix="v",
    ),
    RuntimeLibrary(
        "https://github.com/nginx/nginx",
        lambda: read_program_version("nginx", "-v"),
        tag_prefix="release-",
    ),
    RuntimeLibrary(
        "https://github.com/nodejs/node",
        lambda: read_program_version("node", "--version"),
        tag_prefix="v",
    ),
    RuntimeLibrary(
        "https://github.com/postgres/postgres",
        lambda: read_libpq_version(),
        tag_prefix="REL_",
        tag_separator="_",
    ),
    RuntimeLibrary(
        "https://github.com/libjpeg-turbo/libjpeg-turbo",
        lambda: features.version("libjpeg_turbo"),
    ),
    RuntimeLibrary(
        "https://github.com/freetype/freetype",
        lambda: features.version("freetype2"),
        tag_prefix="VER-",
        tag_separator="-",
    ),
    RuntimeLibrary(
        "https://github.com/uclouvain/openjpeg",
        lambda: features.version("jpg_2000"),
        tag_prefix="v",
    ),
    RuntimeLibrary(
        "https://github.com/harfbuzz/harfbuzz",
        lambda: features.version("harfbuzz"),
    ),
    # WeasyPrint loads the system copies, separate from those Pillow bundles.
    RuntimeLibrary(
        "https://github.com/freetype/freetype",
        lambda: read_system_freetype_version(),
        tag_prefix="VER-",
        tag_separator="-",
    ),
    RuntimeLibrary(
        "https://github.com/harfbuzz/harfbuzz",
        lambda: read_system_harfbuzz_version(),
    ),
]


@dataclass(frozen=True)
class UnmonitoredComponent:
    """A component the application runs but the scan cannot check."""

    name: str
    reason: str  # In French, as shown on the dashboard.


# Components known to run but missing from the inventory, maintained by hand.
# A component moves to RUNTIME_LIBRARIES once a source can match its version.
UNMONITORED_COMPONENTS = [
    UnmonitoredComponent(
        "PROJ, système et embarqué par pyproj",
        "aucune source de vulnérabilités ne le couvre",
    ),
    UnmonitoredComponent(
        "libtiff, libwebp, Little CMS, libavif et zlib-ng, embarqués par Pillow",
        "OSV n'a pas de données sur ces bibliothèques",
    ),
    UnmonitoredComponent(
        "Pango, GLib et fontconfig, chargés par WeasyPrint",
        "OSV n'a pas de données sur ces bibliothèques",
    ),
    UnmonitoredComponent(
        "curl, SQLite et libtiff, embarqués par pyproj",
        "pyproj ne donne pas leurs versions",
    ),
    UnmonitoredComponent(
        "OpenSSL, Kerberos et LDAP, embarqués par psycopg-binary",
        "psycopg ne donne pas leurs versions",
    ),
    UnmonitoredComponent(
        "client psql de la synchronisation nocturne des statistiques",
        "présent uniquement pendant la tâche",
    ),
]


def read_components():
    """Return every library the application runs on, once each."""
    python_components = read_python_components()
    npm_components = read_npm_components()
    geo_components = read_geo_components()
    runtime_components = read_runtime_components()
    components = (
        python_components + npm_components + geo_components + runtime_components
    )
    return sorted(set(components), key=lambda c: (c.ecosystem, c.name))


def read_python_components():
    """Read the packages installed in the current Python environment."""
    return [
        Component(
            canonicalize_name(distribution.name), distribution.version, Ecosystem.PYPI
        )
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
        components.append(Component(name, package["version"], Ecosystem.NPM))
    return components


def read_geo_components():
    """Read the geo libraries loaded in this process, as OSV files them.

    OSV has no entry for these C libraries as such. GDAL's flaws are filed under its
    PyPI package, whose versions follow the library, and GEOS's under its OSS-Fuzz project.
    A fiona wheel embeds its own GDAL, separate from the system one Django loads.
    """
    gdal = gdal_version().decode()
    fiona_gdal = fiona.__gdal_version__
    geos = ".".join(str(part) for part in geos_version_tuple())
    return [
        Component("gdal", gdal, Ecosystem.PYPI),
        Component("gdal", fiona_gdal, Ecosystem.PYPI),
        Component("geos", geos, Ecosystem.OSS_FUZZ),
    ]


def read_runtime_components():
    """Read the versions of `RUNTIME_LIBRARIES`, skipping those not installed here."""
    components = []
    for library in RUNTIME_LIBRARIES:
        version = library.read_version()
        if version:
            tag = library.tag(version)
            components.append(Component(library.repository, tag, Ecosystem.GIT))
    return components


def read_libpq_version():
    """Return the version of the libpq bundled with psycopg, as "18.6"."""
    major, minor = divmod(pq.version(), 10000)  # pq.version() gives 180006.
    return f"{major}.{minor}"


def read_program_version(*command):
    """Return the version a program prints, or None if it isn't installed."""
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        logger.warning("%s is not installed, so it is not scanned.", command[0])
        return None

    # nginx prints its version on stderr, node on stdout.
    output = completed.stdout + completed.stderr
    return re.search(r"\d+\.\d+\.\d+", output).group()


def read_system_freetype_version():
    """Return the version of the system FreeType, or None if it isn't installed."""
    freetype = load_system_library("libfreetype.so.6")
    if freetype is None:
        return None

    # FreeType only reports its version through an initialized library handle.
    handle = ctypes.c_void_p()
    error_code = freetype.FT_Init_FreeType(ctypes.byref(handle))
    if error_code:
        logger.warning(
            "FreeType failed to initialize (error %d), so it is not scanned.",
            error_code,
        )
        return None

    major, minor, patch = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
    freetype.FT_Library_Version(
        handle, ctypes.byref(major), ctypes.byref(minor), ctypes.byref(patch)
    )

    freetype.FT_Done_FreeType(handle)
    return f"{major.value}.{minor.value}.{patch.value}"


def read_system_harfbuzz_version():
    """Return the version of the system HarfBuzz, or None if it isn't installed."""
    harfbuzz = load_system_library("libharfbuzz.so.0")
    if harfbuzz is None:
        return None

    harfbuzz.hb_version_string.restype = ctypes.c_char_p
    return harfbuzz.hb_version_string().decode()


def load_system_library(file_name):
    """Load a C library the way WeasyPrint finds it, or return None if it is absent."""
    try:
        return ctypes.CDLL(file_name)
    except OSError:
        logger.warning("%s is not installed, so it is not scanned.", file_name)
        return None
