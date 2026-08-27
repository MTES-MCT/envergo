from django.db import models


class TchapCredential(models.Model):
    """Single-row store for the Tchap bot's Matrix session.

    This credential should be generated (the first time or after a session revocation) with the tchap_bootstrap command
    """

    user_id = models.CharField("Identifiant utilisateur Matrix", max_length=255)
    device_id = models.CharField("Device ID", max_length=255)
    access_token = models.CharField("Access token", max_length=2048)
    crypto_store = models.BinaryField(
        "Crypto store nio (SQLite file)", null=True, blank=True, editable=False
    )
    updated_at = models.DateTimeField("Mis à jour le", auto_now=True)

    class Meta:
        verbose_name = "Identifiants Tchap"
        verbose_name_plural = "Identifiants Tchap"

    def __str__(self):
        return f"{self.user_id} / {self.device_id}"
