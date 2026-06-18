import logging
import tempfile

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


def detect_mime(file):
    """Detect the MIME type of an uploaded file via libmagic.

    Uses from_file rather than from_buffer because libmagic's buffer-based
    detection cannot identify formats like zip whose metadata is at the
    end of the file.
    """
    if hasattr(file, "temporary_file_path"):
        return magic.from_file(file.temporary_file_path(), mime=True)

    with tempfile.NamedTemporaryFile() as tmp:
        for chunk in file.chunks():
            tmp.write(chunk)
        tmp.flush()
        detected = magic.from_file(tmp.name, mime=True)
    file.seek(0)
    return detected


def validate_mime(file, allowed_mime_types):
    detected = detect_mime(file)
    if detected not in allowed_mime_types:
        logger.warning(
            f"Le fichier téléchargé a un type MIME détecté de {detected}, qui n'est pas dans la liste des types "
            f"autorisés. Son type MIME déclaré est {file.content_type}."
        )
        raise ValidationError("Ce type de fichier n'est pas autorisé.")
