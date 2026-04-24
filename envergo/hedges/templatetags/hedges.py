from django import template

from envergo.hedges.models import LEVELS_OF_CONCERN

register = template.Library()


@register.filter
def level_of_concern_display(value):
    """Return the human-readable label for a level_of_concern value."""
    return dict(LEVELS_OF_CONCERN).get(value, value or "")
