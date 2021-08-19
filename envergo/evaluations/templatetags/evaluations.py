from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def probability(p):
    """Pretty display a probability label."""
    p_labels = [
        "Improbable",
        "Peu probable",
        "Possible",
        "Probable",
        "Très probable",
        "Certain",
    ]
    label = p_labels[p]

    display = f'<span class="probability probability-{p}">{label}</span>'
    return mark_safe(display)


@register.simple_tag
def gauge_angle(p):
    """Fetches the correct svg gauge needle angle."""

    angles = [-79, -47, -16, 16, 48, 79]
    return angles[p]
