import json

from django import template
from django.core.serializers import serialize
from django.db.models import QuerySet
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from envergo.geodata.utils import to_geojson as convert_to_geojson
from envergo.moulinette.models import EPSG_WGS84

register = template.Library()


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
    template_name = (
        f"moulinette/{regulation.slug}/{criterion.slug}_{criterion.result_code}.html"
    )
    context_data = context.flatten()
    context_data.update({
        'regulation': regulation,
        'criterion': criterion
    })
    try:
        content = render_to_string(template_name, context_data)
    except TemplateDoesNotExist:
        content = ""

    return content
