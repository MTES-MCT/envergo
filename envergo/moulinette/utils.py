from pathlib import Path

from django.conf import settings
from django.http import QueryDict


def compute_surfaces(data: QueryDict):
    """Compute all moulinette form surfaces.

    In the legacy version of the moulinette, the user would provide the existing_surface
    and created surface, and the final surface would be computed.

    The form has evoldved and now, the user has to provide the created_surface and
    final surface.

    Since we still need to accomodate for the existing evaluations with legacy format
    form urls, this utility method makes sure all the required surfaces are computed
    and provided to the
    """
    created_surface = data.get("created_surface")
    existing_surface = data.get("existing_surface")
    final_surface = data.get("final_surface")

    # If too many values missing, we can't do anything
    if existing_surface is None and final_surface is None:
        return {}

    if final_surface is None:
        final_surface = int(created_surface) + int(existing_surface)
    elif existing_surface is None:
        existing_surface = int(final_surface) - int(created_surface)

    return {
        "existing_surface": existing_surface,
        "created_surface": created_surface,
        "final_surface": final_surface,
    }


def list_criteria_templates():
    """List all known criteria templates

    With the following form:

    {regulation/{criterion}.html
    """
    from envergo.moulinette.models import REGULATIONS

    templates_path = f"{settings.APPS_DIR}/templates/moulinette"
    for regulation, _label in REGULATIONS:
        regulation_path = f"{templates_path}/{regulation}"
        path = Path(regulation_path)
        files = [f for f in path.iterdir() if f.is_file()]
        for file in files:
            if not file.name.startswith("result_") and not file.name.startswith("_"):
                template = f"{regulation}/{file.name}"
                yield template
