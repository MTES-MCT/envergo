"""Template tags and filters for the hedges app."""

from django import template

from envergo.hedges.models import LEVELS_OF_CONCERN

register = template.Library()

LEVEL_DISPLAY_MAP = dict(LEVELS_OF_CONCERN)


@register.filter
def level_of_concern_display(value):
    """Return the human-readable label for a level_of_concern value."""
    return LEVEL_DISPLAY_MAP.get(value, value or "")
