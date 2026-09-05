import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import CharField
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class GuhRole(models.TextChoices):
    """GUH business role typology.

    Values are stable identifiers stored in analytics (Event.metadata["user_type"]);
    do not change them without a data migration.
    """

    ADMINISTRATOR = "administrator", "Administrateur GUH"
    COORDINATOR = "coordinator", "Coordonnateur GUH"
    INSTRUCTOR = "instructor", "Instructeur consulté"
    GUEST = "guest", "Authentifié sans dossier"
    ANONYMOUS = "anonymous", "Non authentifié"


class UserManager(BaseUserManager):
    """Custom manager for our custom User model."""

    def _create_user(self, email, name, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, name=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, name, password, **extra_fields)

    def create_superuser(self, email, name=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, name, password, **extra_fields)


class User(AbstractUser):
    """Default user for Envergo."""

    objects = UserManager()

    email = models.EmailField(_("Email address"), unique=True)
    name = CharField(_("Name of User"), blank=True, max_length=255)
    access_amenagement = models.BooleanField(
        _("Access amenagement site"), default=False
    )
    access_haie = models.BooleanField(_("Access haie site"), default=False)

    is_coordinator = models.BooleanField(
        "Coordonnateur GUH d'un ou plusieurs départements",
        default=False,
        help_text="""Donne les droits de coordonnateur sur tous les dossiers des départements autorisés pour ce user.
        Si cette case n'est pas cochée, la personne a le statut d'instructeur consulté ou d'invitée.""",
    )
    departments = models.ManyToManyField(
        "geodata.Department",
        verbose_name=_("Departements"),
        related_name="members",
        blank=True,
    )

    username = None  # type: ignore
    first_name = None  # type: ignore
    last_name = None  # type: ignore

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return f"{self.name}"

    @cached_property
    def department_ids(self):
        """Ids of the user's departments.

        Cached because permission checks run once per dossier on list
        pages: a query per call would be an N+1.
        """
        return set(self.departments.values_list("id", flat=True))

    @property
    def has_coordination_access(self):
        """Returns True if the user is a « coordinator »"""
        return self.guh_role in (GuhRole.ADMINISTRATOR, GuhRole.COORDINATOR)

    @property
    def has_instruction_access(self):
        """Returns True if the user is an « instructeur »"""
        return self.guh_role in (
            GuhRole.ADMINISTRATOR,
            GuhRole.COORDINATOR,
            GuhRole.INSTRUCTOR,
        )

    @cached_property
    def guh_role(self):
        """Return the GUH business role of the user."""
        if not self.is_authenticated or not self.is_active:
            return GuhRole.ANONYMOUS

        if self.is_superuser:
            return GuhRole.ADMINISTRATOR

        if not self.access_haie:
            return GuhRole.GUEST

        if self.is_coordinator:
            return GuhRole.COORDINATOR
        has_dossier_access = bool(self.department_ids) or (
            self.invitation_tokens.exists()
        )
        return GuhRole.INSTRUCTOR if has_dossier_access else GuhRole.GUEST

    def get_unique_hash(self):
        """Return unique hash from user email with a salt from env variable"""
        salt_value = settings.HASH_SALT_KEY
        if not salt_value:
            raise ImproperlyConfigured("Missing setting: `HASH_SALT_KEY` is not set")
        key = salt_value.encode()
        return hmac.new(key, self.email.encode(), hashlib.sha256).hexdigest()
