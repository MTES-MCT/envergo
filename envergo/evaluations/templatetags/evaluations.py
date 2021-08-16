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
