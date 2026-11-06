from django import template
from django.utils.html import format_html

from envergo.evaluations.models import RESULTS, TAG_STYLES_BY_RESULT, TagStyleEnum

register = template.Library()


@register.simple_tag
def result_tag(result, result_tag_style: TagStyleEnum = None):
    """Render a result badge, or nothing for a result without a label.

    The markup must never carry the legacy `probability` classes: cached
    evaluation pages still rely on them for their own colours.
    """
    if result_tag_style is None:
        result_tag_style = TAG_STYLES_BY_RESULT[result]

    try:
        result_label = RESULTS[result]
    except KeyError:
        return ""

    badge_classes = "fr-badge fr-badge--no-icon result-badge"
    if result_tag_style.value:
        badge_classes = f"{badge_classes} {result_tag_style.value}"

    return format_html(
        '<span class="{}" data-result="{}">{}</span>',
        badge_classes,
        result,
        result_label,
    )


@register.simple_tag
def gauge_angle(p):
    """Fetches the correct svg gauge needle angle."""

    angles = [-79, -47, -16, 16, 48, 79]
    return angles[p]


@register.simple_tag
def get_from_evaluator_settings(regulation, criterion_slug, setting_name):
    """Returns the values of a given setting from evaluator settings for a given criterion.

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
    values = [
        criterion.evaluator_settings[setting_name]
        for criterion in criteria
        if setting_name in criterion.evaluator_settings
    ]
    return values
