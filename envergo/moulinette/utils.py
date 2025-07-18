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

    if not final_surface:
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
