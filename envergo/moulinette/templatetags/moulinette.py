import json
import logging

from django import template
from django.template import Context, Template
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from envergo.geodata.utils import to_geojson as convert_to_geojson

register = template.Library()


logger = logging.getLogger(__name__)


@register.simple_tag
def to_geojson(obj, geometry_field="geometry"):
    json_obj = convert_to_geojson(obj)
    return mark_safe(json.dumps(json_obj))


@register.simple_tag(takes_context=True)
def show_regulation_body(context, regulation):
    template_name = f"moulinette/{regulation.slug}/result_{regulation.result}.html"
    try:
        content = render_to_string(template_name, context=context.flatten())
    except TemplateDoesNotExist:
        content = ""

    return content


@register.simple_tag(takes_context=True)
def show_criterion_body(context, regulation, criterion):
    """Render a single criterion content.

    We use templates to render the content of a single criterion for a given result code.

    Templates are by default stored on the file system, but can be overriden with
    MoulinetteConfig templates.
    """
    template_name = f"{regulation.slug}/{criterion.slug}_{criterion.result_code}.html"
    full_template_name = f"moulinette/{template_name}"
    context_data = context.flatten()
    context_data.update({"regulation": regulation, "criterion": criterion})

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


@register.simple_tag
def criterion_value(config, criterion, field):
    """Display a criterion static value.

    If this value is overriden in the MoulinetteConfig instance,
    display the config value instead.
    """
    values = config.criteria_values
    key = f"{criterion.unique_slug}__{field}"
    default = getattr(criterion, field, "")
    return mark_safe(values.get(key, default))


@register.simple_tag(takes_context=True)
def moulinette_template(context, template_key, **kwargs):
    """Render a moulinette template.

    This template is rendered with the current context.
    """
    moulinette = context["moulinette"]
    template_obj = moulinette.get_template(template_key)
    if not template_obj:
        logger.warning(
            f"Template {template_key} not found for config {moulinette.config}."
        )
        return ""

    template = Template(template_obj.content)
    content = template.render(context)
    return mark_safe(content)


@register.simple_tag()
def debug(stuff):
    raise 0


@register.simple_tag()
def perimeter_long_name(regulation, perimeter):
    """Display a long name for a given perimeter.

    It will displayed in this kind of sentence:
    "Le projet se trouve dans le périmètre {{ long name }}."
    """
    templates = [
        f"moulinette/{regulation.slug}/_perimeter_long_name.html",
        "moulinette/_perimeter_long_name.html",
    ]
    long_name = render_to_string(templates, {"perimeter": perimeter})
    return long_name
