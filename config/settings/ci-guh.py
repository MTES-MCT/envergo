"""
With these settings, tests run faster.
"""

from .ci import *  # noqa
from .ci import env

# Your stuff...
# ------------------------------------------------------------------------------
ENVERGO_AMENAGEMENT_DOMAIN = env(
    "DJANGO_ENVERGO_AMENAGEMENT_DOMAIN", default="envergo.beta.gouv.fr"
)
ENVERGO_HAIE_DOMAIN = "localhost"
