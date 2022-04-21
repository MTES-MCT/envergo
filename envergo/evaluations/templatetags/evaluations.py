from django import template
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS

register = template.Library()


PROBA_CSS = {
    RESULTS.soumis: 4,
    RESULTS.action_requise: 3,
    RESULTS.non_soumis: 1,
    RESULTS.non_disponible: 2,
    RESULTS.non_applicable: 2,
}


@register.simple_tag
def probability(criterion):
    """Pretty display a probability label."""

    if criterion.probability:
        label = criterion.get_probability_display()
        css_class = criterion.probability
    else:
        css_class = PROBA_CSS.get(criterion.result)
        label = criterion.get_result_display()

    display = f'<span class="fr-tag probability probability-{css_class}">{label}</span>'
    return mark_safe(display)


@register.simple_tag
def result_tag(result):

    proba_level = PROBA_CSS.get(result)
    result_label = RESULTS[result]
    display = f'<span class="fr-tag probability probability-{proba_level}">{result_label}</span>'
    return mark_safe(display)


@register.simple_tag
def gauge_angle(p):
    """Fetches the correct svg gauge needle angle."""

    angles = [-79, -47, -16, 16, 48, 79]
    return angles[p]
