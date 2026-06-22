"""Template tags and filters for the hedges app."""

from django import template

from envergo.hedges.models import LEVELS_OF_CONCERN
from envergo.moulinette.regulations import HaieCriterionCategory

register = template.Library()

LEVEL_DISPLAY_MAP = dict(LEVELS_OF_CONCERN)


@register.filter
def level_of_concern_display(value):
    """Return the human-readable label for a level_of_concern value."""
    return LEVEL_DISPLAY_MAP.get(value, value or "")


@register.filter
def hedges_category(hedge_data, category):
    to_remove = hedge_data.hedges().to_remove()
    if category == HaieCriterionCategory.hru:
        return to_remove.hru()
    elif category == HaieCriterionCategory.ru:
        return to_remove.ru()
    else:
        # category == HaieCriterionCategory.l350_3:
        return to_remove.l350_3()
