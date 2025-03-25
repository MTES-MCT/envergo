from django import template
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS, TagStyleEnum

register = template.Library()


@register.simple_tag
def result_tag(result, result_tag_style: TagStyleEnum):
    try:
        result_label = RESULTS[result]
        display = (
            f'<span class="fr-tag probability probability-{result_tag_style.value} probability-{result}">'
            f"{result_label}</span>"
        )
    except KeyError:
        display = ""
    return mark_safe(display)


@register.simple_tag
def gauge_angle(p):
    """Fetches the correct svg gauge needle angle."""

    angles = [-79, -47, -16, 16, 48, 79]
    return angles[p]
