"""List the libraries the running application is made of."""

import json
from dataclasses import dataclass
from importlib.metadata import distributions

from django.conf import settings
from packaging.utils import canonicalize_name

NPM_LOCKFILE = "package-lock.json"


@dataclass(frozen=True)
class Component:
    """One library at the exact version the application uses."""

    name: str
    version: str
    ecosystem: str  # OSV ecosystem name: "PyPI" or "npm".


def read_components():
    """Return every installed Python package and every locked npm package, once each."""
    components = read_python_components() + read_npm_components()
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
