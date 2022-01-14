from django import template
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS

register = template.Library()


@register.simple_tag
def probability(p):
    """Pretty display a probability label."""
    p_labels = [
        "Improbable",
        "Peu probable",
        "Possible",
        "Probable",
        "Seuil franchi",
        "Seuil franchi",
    ]
    label = p_labels[p]

    display = f'<span class="fr-tag probability probability-{p}">{label}</span>'
    return mark_safe(display)


@register.simple_tag
def result_tag(evaluation):

    result = evaluation.get_result_display()
    proba_css = {
        RESULTS.soumis: 4,
        RESULTS.action_requise: 3,
        RESULTS.non_soumis: 2,
    }
    proba_level = proba_css.get(evaluation.result)
    display = (
        f'<span class="fr-tag probability probability-{proba_level}">{result}</span>'
    )
    return mark_safe(display)


@register.simple_tag
def gauge_angle(p):
    """Fetches the correct svg gauge needle angle."""

    angles = [-79, -47, -16, 16, 48, 79]
    return angles[p]
