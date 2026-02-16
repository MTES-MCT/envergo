import json
import logging
import string
from datetime import date
from decimal import Decimal

from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.forms.widgets import NumberInput
from django.template import Context, Template
from django.template.defaultfilters import floatformat
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string
from django.utils.formats import date_format
from django.utils.safestring import mark_safe

from envergo.geodata.utils import to_geojson as convert_to_geojson
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations import HedgeDensityMixin
from envergo.moulinette.utils import get_moulinette_class_from_site

register = template.Library()

logger = logging.getLogger(__name__)


@register.simple_tag
def to_geojson(obj, geometry_field="geometry"):
    json_obj = convert_to_geojson(obj)
    return mark_safe(json.dumps(json_obj))


@register.simple_tag(takes_context=True)
def show_moulinette_form(context):
    """Display the moulinette form.

    We do so by selecting the correct template depending on the current domain.
    """
    MoulinetteClass = get_moulinette_class_from_site(context["request"].site)
    moulinette = MoulinetteClass({})
    template_name = moulinette.get_form_template()

    template = get_template(template_name)
    content = template.render(context.flatten())
    return content


def render_from_moulinette_templates(context, template_name):
    """Render a given moulinette template.

    By default, templates are stored on the file system, but we added the possibility
    to store html templates in the database, to override some templates on a
    department basis.
    """
    full_template_name = f"moulinette/{template_name}"
    context_data = context.flatten()  # context must be a dict, not RequestContext
    moulinette_templates = context["moulinette"].templates
    if template_name in moulinette_templates:
        template_content = moulinette_templates[template_name].content
        content = Template(template_content).render(Context(context_data))
    else:
        try:
            content = render_to_string((full_template_name,), context_data)
        except TemplateDoesNotExist:
            content = ""

    return content


@register.simple_tag(takes_context=True)
def show_regulation_body(context, regulation):
    """Render the main regulation content block."""

    template_name = f"{regulation.slug}/result_{regulation.result}.html"
    content = render_from_moulinette_templates(context, template_name)

    return content


@register.simple_tag(takes_context=True)
def show_criterion_body(context, regulation, criterion):
    """Render a single criterion content."""

    template_name = f"{regulation.slug}/{criterion.slug}_{criterion.result_code}.html"
    content = render_from_moulinette_templates(context, template_name)

    return content


@register.simple_tag
def criterion_value(criterion, field):
    """Display a criterion static value."""
    value = getattr(criterion, field, "")
    return mark_safe(value)


@register.simple_tag(takes_context=True)
def criterion_template(context, template_key, **kwargs):
    """Render a criterion-level moulinette template.

    This template is rendered with the current context.
    """
    criterion = context["criterion"]
    template_obj = criterion.get_template(template_key)
    if not template_obj:
        logger.warning(f"Template {template_key} not found for criterion {criterion}.")
        return ""

    template = Template(template_obj.content)
    content = template.render(context)
    return mark_safe(content)


@register.simple_tag()
def debug(stuff):
    raise 0


@register.simple_tag()
def perimeter_detail(regulation):
    """Display the perimeter short description with links."""

    perimeters = regulation.perimeters.all()
    if len(perimeters) == 1:
        templates = [
            f"moulinette/{regulation.slug}/_one_perimeter_detail.html",
            "moulinette/_one_perimeter_detail.html",
        ]
        detail = render_to_string(templates, {"perimeter": perimeters[0]})
    else:
        templates = [
            f"moulinette/{regulation.slug}/_several_perimeters_details.html",
            "moulinette/_several_perimeters_details.html",
        ]
        detail = render_to_string(templates, {"perimeters": perimeters})

    return mark_safe(detail)


@register.filter
def ends_with_punctuation(sentence):
    trimmed_sentence = sentence.strip() if sentence else sentence
    return trimmed_sentence[-1] in string.punctuation if trimmed_sentence else False


@register.simple_tag()
def field_summary(field):
    """User friendly display of the field value.

    The evaluation page displays a summary of all the user provided data that
    lead to the evaluation result.

    This tag is used to format a single field from the additional or optional forms.
    """
    value_help_text = None
    if hasattr(field.field, "get_display_value"):
        value = field.field.get_display_value(field.value())
    elif hasattr(field.field, "choices"):
        value = dict(field.field.choices).get(field.value(), field.value())
        if isinstance(value, dict):
            value_help_text = value["help_text"]
            value = value["label"]
    else:
        value = field.value()

    # This should not happen
    if value is None:
        value = ""

    # Try to add thousands separator
    if isinstance(value, (int, float, Decimal)):
        value = floatformat(value, "g")

    # Some values are str, from fields with NumberInput,
    # or from TextInput widget but numeric mode
    # or from fields with TextInput but should not be displayed as an integer
    # exemple :
    # - lineaire_total in moulinette/regulation/conditionnalitepac.py : numeric mode
    # - numero_pacage in moulinette/regulation/ep.py : not integer
    # TODO : use NumberInput for fields waiting for digits ?
    elif (
        isinstance(value, str)
        and value.isdigit()
        and (
            field.field.widget is NumberInput
            or field.field.widget.attrs.get("inputmode") == "numeric"
        )
    ):
        try:
            value = intcomma(value)
        except (TypeError, ValueError):
            pass

    label = field.label
    if hasattr(field.field, "display_label"):
        # if there is a display_label, use it instead of the field label
        label = field.field.display_label
    elif not ends_with_punctuation(field.label):
        # else, add a colon at the end of the label if it doesn't end with punctuation
        label = f"{field.label} :"

    value = (
        f"{value} {field.field.display_unit}"
        if hasattr(field.field, "display_unit") and field.field.display_unit
        else value
    )
    html = f"<strong>{label}</strong> {value}"
    if hasattr(field.field, "display_help_text"):
        if field.field.display_help_text:
            html += f' <br /><span class="fr-hint-text">{field.field.display_help_text}</span>'
    elif field.help_text:
        html += f' <br /><span class="fr-hint-text">{field.help_text}</span>'
    if value_help_text:
        html += f' <br /><span class="fr-hint-text">{value_help_text}</span>'

    return mark_safe(html)


@register.simple_tag(takes_context=True)
def show_haie_moulinette_result(context, moulinette, plantation_evaluation):
    """Render the global moulinette result content."""
    context_data = context.flatten()
    context_data.update(plantation_evaluation.get_context())
    regime = "regime_unique" if moulinette.config.single_procedure else "droit_constant"
    template_name = f"haie/moulinette/result/{regime}/{moulinette.result}.html"
    try:
        content = render_to_string((template_name,), context_data)
    except TemplateDoesNotExist:
        logger.error(
            "Template for GUH global result is missing.",
            extra={"result": moulinette.result, "template_name": template_name},
        )
        content = ""

    return content


@register.simple_tag(takes_context=True)
def show_plantation_result(context, plantation_evaluation):
    """Render the global plantation result content."""
    context_data = context.flatten()
    template_name = (
        f"haie/moulinette/plantation_result/{plantation_evaluation.global_result}.html"
    )

    if (
        context.get("is_alternative", False)
        and not plantation_evaluation.display_for_alternatives
    ):
        html = ""
    else:
        try:
            content = render_to_string((template_name,), context_data)
            html = f'<div class="alt fr-p-3w fr-mb-3w">{content}</div>'
        except TemplateDoesNotExist:
            logger.error(
                "Template for GUH global plantation result is missing.",
                extra={
                    "result": plantation_evaluation.global_result,
                    "template_name": template_name,
                },
            )
            html = ""
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def show_haie_moulinette_liability_info(context, result):
    """Render the liability_info content depending on the moulinette result."""

    template_name = f"haie/moulinette/liability_info/{result}.html"
    try:
        content = render_to_string((template_name,), context.flatten())
    except TemplateDoesNotExist:
        logger.error(
            f"Template for GUH liability info is missing. {result}",
            extra={"result": result, "template_name": template_name},
        )
        content = ""

    return content


@register.simple_tag(takes_context=True)
def show_haie_plantation_liability_info(context, plantation_evaluation):
    """Render the liability_info content depending on the result and plantation evaluation for the result p page."""

    template_name = f"haie/moulinette/plantation_liability_info/{plantation_evaluation.result_code}.html"
    try:
        content = render_to_string((template_name,), context.flatten())
    except TemplateDoesNotExist:
        logger.error(
            f"Template for GUH liability info is missing. {plantation_evaluation.result_code}",
            extra={
                "plantation_evaluation": plantation_evaluation.result_code,
                "template_name": template_name,
            },
        )
        content = ""

    return content


@register.simple_tag(takes_context=True)
def show_haie_plantation_evaluation(context, moulinette, plantation_evaluation):
    """Render the evaluation of the plantation project"""

    context_data = context.flatten()
    context_data["plantation_evaluation"] = plantation_evaluation
    context_data.update(plantation_evaluation.get_context())

    template_name = (
        f"haie/moulinette/plantation_evaluation/{plantation_evaluation.result}.html"
    )

    try:
        content = render_to_string((template_name,), context_data)
    except TemplateDoesNotExist:
        logger.error(
            f"Template for GUH plantation evaluation is missing. {plantation_evaluation.result}",
            extra={
                "plantation_evaluation": plantation_evaluation.result,
                "template_name": template_name,
            },
        )
        content = ""

    return content


@register.filter
def requires_hedge_density(criterion):
    return isinstance(criterion._evaluator, HedgeDensityMixin)


@register.filter
def display_remove_only_haies_field(field):
    """Display the haies field value as read only with only the hedges to remove."""
    hedge_data = field.field.clean(field.value())
    value = floatformat(hedge_data.length_to_remove(), "0g")
    html = f"<strong>Linéaire de haies à détruire :</strong> {value} m"
    return mark_safe(html)


@register.simple_tag
def humanize_motif(motif):
    return dict(MOTIF_CHOICES).get(motif, "Motif non défini")


@register.filter
def display_validity_range(validity_range):
    """Format a DateRange for human-friendly display.

    Returns an empty string when the range is None (always valid), so the
    caller can hide the entire line with {% if ... %}.
    """
    if validity_range is None:
        return ""

    lower = validity_range.lower
    upper = validity_range.upper
    fmt = "d/m/Y"

    if lower and upper:
        return f"du {date_format(lower, fmt)} au {date_format(upper, fmt)}"

    if upper:
        return f"jusqu'au {date_format(upper, fmt)}"

    # Only a lower bound
    if lower <= date.today():
        return f"depuis le {date_format(lower, fmt)}"
    return f"à partir du {date_format(lower, fmt)}"
