import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import urlize as _urlize
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlize_html(value, blank=True, autoescape=True):
    """Convert URLs in plain text into clickable links."""
    # Remove existing tag a before urlize
    clean = re.compile("</?a.*?>")
    result = re.sub(clean, "", value)
    result = _urlize(result, nofollow=True, autoescape=autoescape)
    if blank:
        result = result.replace("<a", '<a target="_blank"')
    return mark_safe(result)
