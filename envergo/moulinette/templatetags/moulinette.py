import json
import logging

from django import template
from django.template import Context, Template
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string
from django.utils.safestring import mark_safe

from envergo.geodata.utils import to_geojson as convert_to_geojson
from envergo.moulinette.models import get_moulinette_class_from_site

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
    template_name = MoulinetteClass.get_form_template()

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


@register.simple_tag()
def field_summary(field):
    """User friendly display of the field value.

    The evaluation page displays a summary of all the user provided data that
    lead to the evaluation result.

    This tag is used to format a single field from the additional or optional forms.
    """
    if hasattr(field.field, "choices"):
        value = dict(field.field.choices).get(field.value(), field.value())
    else:
        value = field.value()

    html = f"<strong>{field.label}</strong> {value}"
    if field.help_text:
        html += f' <br /><span class="fr-hint-text">{field.help_text}</span>'

    return mark_safe(html)
