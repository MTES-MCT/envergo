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


@register.simple_tag
def get_min_threshold(regulation, criterion_slug):
    """Returns the minimum threshold from evaluator settings for a given criterion.

    This method is useful when there are multiple instances of the same criterion in a regulation. e.g. two SAGE
    """
    if not (
        "_prefetched_objects_cache" in regulation.__dict__
        and "criteria" in regulation.__dict__["_prefetched_objects_cache"]
    ):
        raise ValueError("Regulation must be prefetched with criteria")

    criteria = [
        criterion
        for criterion in regulation.__dict__["_prefetched_objects_cache"]["criteria"]
        if criterion.slug == criterion_slug
    ]
    thresholds = [
        criterion.evaluator_settings.get("threshold", 0) for criterion in criteria
    ]
    return min(thresholds) if thresholds else 0
