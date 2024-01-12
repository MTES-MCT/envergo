def compute_surfaces(data):
    # The user MUST provide the total final surface
    # However, in a previous version of the form, the user
    # would provide the existing surface and the created surface, and
    # the final surface was computed.
    # So we have to accomodate for bookmarked simulation with the old
    # data format
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
