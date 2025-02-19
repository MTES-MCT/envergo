import logging

from django.contrib.auth.backends import ModelBackend

from envergo.utils.tools import get_site_literal

logger = logging.getLogger(__name__)


class AuthBackend(ModelBackend):
    """Custom Backend for EnvErgo.

    Login requirements are different for Amenagement and Haies.
    """

    def authenticate(self, request, *args, **kwargs):
        self.site_literal = get_site_literal(request.site)
        return super().authenticate(request, *args, **kwargs)

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
                        getattr(user, "is_confirmed_by_admin", True),
                    )
                )
        else:
            # Happen only during tests when using force_login
            can_auth = super().user_can_authenticate(user)

        return can_auth
