import logging

from django.contrib.auth.backends import ModelBackend

from envergo.utils.tools import get_site_literal

logger = logging.getLogger(__name__)


class AuthBackend(ModelBackend):
    """Custom Backend for Envergo.

    Login requirements are different for Amenagement and Haies.
    """

    def authenticate(self, request, *args, **kwargs):
        self.site_literal = get_site_literal(request.site)
        return super().authenticate(request, *args, **kwargs)

    def has_perm(self, user_obj, perm, obj=None):
        """Object-level permissions for PetitionProject.

        Exposes the project's computed permissions through Django's standard
        ``user.has_perm('petitions.<action>_petitionproject', project)`` API, so
        views/templates/DRF can rely on the auth framework instead of ad-hoc
        method calls.

        The permission is *computed* from the user's departments/tokens (see
        ``PetitionProject.has_view_permission`` / ``has_change_permission``), it
        is never a stored grant. Note that an auth backend can only *grant* a
        permission, never deny one: therefore the model-level
        ``view_petitionproject`` / ``change_petitionproject`` permissions must
        NOT be assigned to any user/group, otherwise they would leak here
        regardless of ``obj``.
        """
        # Local import to avoid a circular import at module load time.
        from envergo.petitions.models import PetitionProject

        if obj is not None and isinstance(obj, PetitionProject):
            if perm == "petitions.view_petitionproject":
                return obj.has_view_permission(user_obj)
            if perm == "petitions.change_petitionproject":
                return obj.has_change_permission(user_obj)
        return super().has_perm(user_obj, perm, obj)

    def user_can_authenticate(self, user):

        if getattr(user, "is_superuser", False):
            can_auth = super().user_can_authenticate(user)
        elif hasattr(self, "site_literal"):
            if self.site_literal == "amenagement":
                can_auth = all(
                    (
                        getattr(user, "access_amenagement", True),
                        getattr(user, "is_active", True),
                    )
                )
            else:
                can_auth = all(
                    (
                        getattr(user, "access_haie", True),
                        getattr(user, "is_active", True),
                    )
                )
        else:
            # Happen only during tests when using force_login
            can_auth = super().user_can_authenticate(user)

        return can_auth
