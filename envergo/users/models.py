from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import CharField
from django.utils.translation import gettext_lazy as _


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

    is_instructor = models.BooleanField(
        "En charge de l'instruction sur les départements",
        default=False,
        help_text="""Donne accès aux actions instructeur sur tous les dossiers des départements autorisés pour ce user.
        Si cette case n'est pas cochée, la personne a le statut d'invitée.""",
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

    def is_involved_in_guh(self):
        """Returns True if user has instructor right or if user has department or token"""
        return any(
            (
                self.is_instructor,
                self.departments.defer("geometry").exists(),
                self.invitation_tokens.exists(),
            )
        )
