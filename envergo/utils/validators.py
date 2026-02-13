import logging

import magic
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

logger = logging.getLogger(__name__)


class NoIdnEmailValidator(EmailValidator):
    """
    Our email sending tool Brevo do not support Internationalized Domain Names (IDN).
    This validator is a subclass of Django's EmailValidator that raises a validation error if there is diacritics,
    ligatures or non-Latin character in the domain name.
    """

    def __call__(self, value):
        # The maximum length of an email is 320 characters per RFC 3696
        # section 3.
        if not value or "@" not in value or len(value) > 320:
            raise ValidationError(self.message, code=self.code, params={"value": value})

        user_part, domain_part = value.rsplit("@", 1)

        if not self.user_regex.match(user_part):
            raise ValidationError(self.message, code=self.code, params={"value": value})

        if domain_part not in self.domain_allowlist and not self.validate_domain_part(
            domain_part
        ):
            if self.validate_domain_part(domain_part):
                return

            raise ValidationError(self.message, code=self.code, params={"value": value})


def validate_mime(file, allowed_mime_types):
    detected = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    if detected not in allowed_mime_types:
        logger.warning(
            f"Le fichier téléchargé a un type MIME détecté de {detected}, qui n'est pas dans la liste des types "
            f"autorisés. Son type MIME déclaré est {file.content_type}."
        )
        raise ValidationError("Ce type de fichier n'est pas autorisé")
