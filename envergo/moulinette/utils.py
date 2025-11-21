import os
from pathlib import Path

from django.conf import settings
from django.http import QueryDict


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
    for engine in settings.TEMPLATES:
        dirs = engine.get("DIRS", [])
        for base_dir in dirs:
            scan_dir = (
                os.path.join(base_dir, template_subdir) if template_subdir else base_dir
            )
            if not os.path.exists(scan_dir):
                continue
            for root, _, files in os.walk(scan_dir):
                for file in files:
                    if file.endswith(extension):
                        # Make template path relative to base_dir
                        rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                        # Use forward slashes for Django template loader
                        rel_path = rel_path.replace(os.path.sep, "/")
                        templates.add(rel_path)

    # Return sorted list of tuples (value, display_name)
    return [("", "---------")] + sorted((t, t) for t in templates)
