import os
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.http import QueryDict
from django.template import engines
from django.utils._os import safe_join

from envergo.urlmappings.utils import unfold_url


class MoulinetteUrl:
    """A url with valid moulinette simulation parameters."""

    def __init__(self, url):
        self.url = unfold_url(url)

    @property
    def querydict(self):
        url = urlparse(self.url)
        qd = QueryDict(url.query, mutable=True)
        return qd

    @property
    def params(self):
        return self.querydict.dict()

    def get_moulinette(self):
        try:
            MoulinetteClass = get_moulinette_class_from_url(self.url)
            data = self.params
            moulinette_data = {"initial": data, "data": data}
            moulinette = MoulinetteClass(moulinette_data)
            return moulinette
        except RuntimeError:
            moulinette = None

        return moulinette

    def is_valid(self):
        """Check if the moulinette url is valid.

        A moulinette url is valid if it can create a valid Moulinette with a valid url.
        """
        moulinette = self.get_moulinette()
        return moulinette and moulinette.is_valid()

    def __getitem__(self, key):
        return self.querydict[key]


def get_moulinette_class_from_site(site):
    """Return the correct Moulinette class depending on the current site."""
    from envergo.moulinette.models import MoulinetteAmenagement, MoulinetteHaie

    domain_class = {
        settings.ENVERGO_AMENAGEMENT_DOMAIN: MoulinetteAmenagement,
        settings.ENVERGO_HAIE_DOMAIN: MoulinetteHaie,
    }
    cls = domain_class.get(site.domain, None)
    if cls is None:
        raise RuntimeError(f"Unknown site for domain {site.domain}")
    return cls


def get_moulinette_class_from_url(url):
    """Return the correct Moulinette class depending on the current site."""
    from envergo.moulinette.models import MoulinetteAmenagement, MoulinetteHaie

    if "envergo" in url:
        cls = MoulinetteAmenagement
    elif "haie" in url:
        cls = MoulinetteHaie
    else:
        raise RuntimeError("Cannot find the moulinette to use")
    return cls


def compute_surfaces(data: QueryDict):
    """Compute all moulinette form surfaces.

    In the legacy version of the moulinette, the user would provide the existing surface
    and created surface, and the final surface would be computed.

    The form has evolved and now, the user has to provide the created_surface and
    final surface.

    Since we still need to accomodate for the existing evaluations with legacy format
    form urls, this utility method makes sure all the required surfaces are computed
    and provided to the moulinette
    """
    created_surface = data.get("created_surface")
    existing_surface = data.get("existing_surface")
    final_surface = data.get("final_surface")

    # If too many values missing, we can't do anything
    if existing_surface is None and final_surface is None:
        return {}

    if final_surface is None:
        try:
            final_surface = str(int(created_surface) + int(existing_surface))
        except (ValueError, TypeError):
            final_surface = None
    else:
        # if final_surface is provided, we compute the existing surface (even if it is provided to avoid inconsistency)
        try:
            existing_surface = str(int(final_surface) - int(created_surface))
        except (ValueError, TypeError):
            existing_surface = None

    return {
        "existing_surface": existing_surface,
        "created_surface": created_surface,
        "final_surface": final_surface,
    }


def list_moulinette_templates():
    """List all known templates for moulinette result rendering.

    (regulation and criteria results).

    Returns a list of strings like:

    {regulation/{template_name}.html
    """
    from envergo.moulinette.models import REGULATIONS

    templates_path = f"{settings.APPS_DIR}/templates/moulinette"
    templates = []
    for regulation, _label in REGULATIONS:
        regulation_path = f"{templates_path}/{regulation}"
        path = Path(regulation_path)
        files = [f for f in path.iterdir() if f.is_file()]
        for file in files:
            if not file.name.startswith("_"):
                template = f"{regulation}/{file.name}"
                templates.append(template)

    return sorted(templates)


def get_template_choices(template_subdir=None, extension=".html"):
    """
    Returns a list of (template_path, template_name) tuples for use in a model choices.
    - template_subdir: optional subdirectory inside templates to scan
    - extension: filter by file extension (default .html)
    """
    templates = set()

    # Loop over all TEMPLATE_DIRS
    for engine in engines.all():
        for base_dir in engine.template_dirs:
            scan_dir = (
                safe_join(base_dir, template_subdir) if template_subdir else base_dir
            )
            if not os.path.exists(scan_dir):
                continue
            for root, _, files in os.walk(scan_dir):
                for file in files:
                    if file.endswith(extension):
                        # Make template path relative to base_dir
                        rel_path = os.path.relpath(safe_join(root, file), base_dir)
                        # Use forward slashes for Django template loader
                        rel_path = rel_path.replace(os.path.sep, "/")
                        templates.add(rel_path)

    # Return sorted list of tuples (value, display_name)
    return [("", "---------")] + sorted((t, t) for t in templates)
