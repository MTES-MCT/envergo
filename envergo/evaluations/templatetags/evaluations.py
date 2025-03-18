from django import template
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS

register = template.Library()

# CSS classes for each probability level
# 1: green, 2: grey, 3: yellow, 4: light red, 5: orange, 6 strong red
PROBA_CSS = {
    RESULTS.soumis: 4,
    RESULTS.soumis_ou_pac: 4,
    RESULTS.action_requise: 3,
    RESULTS.non_soumis: 1,
    RESULTS.non_disponible: 2,
    RESULTS.non_applicable: 2,
    RESULTS.cas_par_cas: 5,
    RESULTS.systematique: 4,
    RESULTS.non_concerne: 1,
    RESULTS.a_verifier: 3,
    RESULTS.iota_a_verifier: 3,
    RESULTS.interdit: 6,
    RESULTS.non_active: 2,
    RESULTS.derogation_inventaire: 4,
    RESULTS.derogation_simplifiee: 4,
    RESULTS.dispense: 1,
}

_missing_results = [key for (key, label) in RESULTS if key not in PROBA_CSS]
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in PROBA_CSS: {_missing_results}"
    )


@register.simple_tag
def result_tag(result):
    proba_level = PROBA_CSS.get(result, result)
    try:
        result_label = RESULTS[result]
        display = (
            f'<span class="fr-tag probability probability-{proba_level} probability-{result}">'
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
