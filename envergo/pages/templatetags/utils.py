import re
import warnings
from collections.abc import Iterable, Mapping

from django import template
from django.db.models import NOT_PROVIDED
from django.forms.widgets import (
    CheckboxInput,
    CheckboxSelectMultiple,
    FileInput,
    HiddenInput,
    RadioSelect,
    Select,
)
from django.http import QueryDict
from django.template.base import TemplateSyntaxError
from django.template.defaultfilters import stringfilter
from django.template.loader import get_template
from django.utils.dateparse import parse_datetime
from django.utils.deprecation import RemovedInDjango51Warning
from django.utils.html import strip_tags
from django.utils.html import urlize as _urlize

from envergo.utils.fields import HedgeChoiceField

register = template.Library()


@register.filter
def add_classes(field, classes):
    """Add some classes to the field widget html."""
    css_classes = field.field.widget.attrs.get("class", "").split(" ")
    all_classes = sorted(list(set(classes.split(" ")) | set(css_classes)))
    all_classes.remove("")  # Prevent unwanted space in class list
    ret = field.as_widget(attrs={"class": " ".join(all_classes)})
    return ret


@register.inclusion_tag("admin/submit_line.html", takes_context=True)
def envergo_submit_row(context):
    """Custom submit line for admin edition templates.

    We only display a single "save" button that do not leave the edit page
    afterwards.
    """
    show_save = context.get("show_save", True)

    add = context["add"]
    change = context["change"]
    is_popup = context["is_popup"]
    show_save = context.get("show_save", True)
    has_add_permission = context["has_add_permission"]
    has_change_permission = context["has_change_permission"]
    has_editable_inline_admin_formsets = context["has_editable_inline_admin_formsets"]
    can_save = (
        (has_change_permission and change)
        or (has_add_permission and add)
        or has_editable_inline_admin_formsets
    )
    can_change = has_change_permission or has_editable_inline_admin_formsets
    context.update(
        {
            "can_change": can_change,
            "show_save": show_save and can_save,
            "show_close": not (show_save and can_save),
            "show_delete_link": (
                not is_popup
                and context["has_delete_permission"]
                and change
                and context.get("show_delete", True)
            ),
        }
    )
    return context


@register.filter
def to_list(item):
    """turn a single item into a list"""
    return [item]


@register.filter
def add_string(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)


@register.filter
def is_type(value, type_name):
    return type(value).__name__ == type_name


@register.filter
def get_item(dictionary, key):
    return dictionary[key]


@register.filter
def as_hidden(field):
    """Render the field as a hidden input without modifying the original widget."""
    return field.as_widget(widget=HiddenInput())


@register.filter
def get_choice_label(choices, value):
    """Return human-readable label for a given choice value."""
    return dict(choices).get(value, value)


@register.filter
def to_datetime(value):
    """Parse ISO string and return datetime.datetime or datetime.timezone"""
    return parse_datetime(value)


@register.filter
def choice_default_label(model, field_name):
    """Return the label of the default choice for a model choice field."""
    field = model._meta.get_field(field_name)
    if field.default is NOT_PROVIDED:
        default = ""
    else:
        default = field.default
    return dict(field.choices).get(default, default)


@register.filter(is_safe=True)
@stringfilter
def urlize_html(value, blank=True):
    """Convert URLs in text into clickable links, stripping any HTML markup.

    This filter is mainly used to parse and sanitized messages fetched from DS.

    DS sends messages in inconsistent formats. Sometimes html, sometimes markdown.

    We strip all tags while preserving paragraph
    boundaries as newlines (so the downstream |linebreaks filter recreates the
    visual structure), then linkify any URLs found in the resulting plain text.

    This is a sensitive piece of code, since it's used to sanitize content that
    we get from a third party, but it must output `safe`
    content that will be integrated as-is in the page.
    """
    # Strip existing <a> tags, keeping only the href value.
    # We use a regex instead of BeautifulSoup to avoid HTML entity decoding
    # (e.g. &numero being converted to №).
    text = re.sub(
        r"""
            <a\s            # opening <a tag followed by a space
            [^>]*           # any attributes before href
            href\s*=\s*     # href attribute with optional whitespace around =
            ["']            # opening quote
            ([^"']*)        # everything that is not a quote, capture the URL
            ["']            # closing quote
            [^>]*>          # any attributes after href, then close tag
            .*?             # link text (non-greedy)
            </a>            # closing tag
        """,
        r"\1",
        value,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    # Convert block-level HTML boundaries to newlines before stripping tags,
    # so paragraph structure is preserved through the |linebreaks filter.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(?:p|div|h[1-6]|li|tr|blockquote)>",
        "\n\n",
        text,
        flags=re.IGNORECASE,
    )

    # Strip all remaining HTML tags.
    text = strip_tags(text)

    # Collapse runs of multiple blank lines into a single paragraph break,
    # preventing |linebreaks from generating empty paragraphs.
    text = re.sub(r"\n(\s*\n)+", "\n\n", text)
    text = text.strip()

    result = _urlize(text, nofollow=True, autoescape=True)
    if blank:
        result = result.replace("<a", '<a target="_blank" rel="noopener"')
    return result


@register.simple_tag(name="querystring", takes_context=True)
def querystring(context, *args, **kwargs):
    """
    Copy from django 5.1 querystring builtin templatetag
    https://github.com/django/django/blob/4702b36120ea4c736d3f6b5595496f96e0021e46/django/template/defaulttags.py#L1286

    Build a query string using `args` and `kwargs` arguments.

    This tag constructs a new query string by adding, removing, or modifying
    parameters from the given positional and keyword arguments. Positional
    arguments must be mappings (such as `QueryDict` or `dict`), and
    `request.GET` is used as the starting point if `args` is empty.

    Keyword arguments are treated as an extra, final mapping. These mappings
    are processed sequentially, with later arguments taking precedence.

    Passing `None` as a value removes the corresponding key from the result.
    For iterable values, `None` entries are ignored, but if all values are
    `None`, the key is removed.

    A query string prefixed with `?` is returned.

    Raise TemplateSyntaxError if a positional argument is not a mapping or if
    keys are not strings.

    For example::

        {# Set a parameter on top of `request.GET` #}
        {% querystring foo=3 %}

        {# Remove a key from `request.GET` #}
        {% querystring foo=None %}

        {# Use with pagination #}
        {% querystring page=page_obj.next_page_number %}

        {# Use a custom ``QueryDict`` #}
        {% querystring my_query_dict foo=3 %}

        {# Use multiple positional and keyword arguments #}
        {% querystring my_query_dict my_dict foo=3 bar=None %}
    """

    warnings.warn(
        "This template tag is a copy of querystring template tag implemented in django 5.1."
        "Remove this when update.",
        category=RemovedInDjango51Warning,
    )
    if not args:
        args = [context.request.GET]
    params = QueryDict(mutable=True)
    for d in [*args, kwargs]:
        if not isinstance(d, Mapping):
            raise TemplateSyntaxError(
                "querystring requires mappings for positional arguments (got "
                "%r instead)." % d
            )
        items = d.lists() if isinstance(d, QueryDict) else d.items()
        for key, value in items:
            if not isinstance(key, str):
                raise TemplateSyntaxError(
                    "querystring requires strings for mapping keys (got %r "
                    "instead)." % key
                )
            if value is None:
                params.pop(key, None)
            elif isinstance(value, Iterable) and not isinstance(value, str):
                # Drop None values; if no values remain, the key is removed.
                params.setlist(key, [v for v in value if v is not None])
            else:
                params[key] = value
    query_string = params.urlencode() if params else ""
    return f"?{query_string}"


@register.inclusion_tag("_truncated_comment.html")
def truncated_comment(text, uid, limit=50):
    """
    Display a truncated comment with DSFR-compatible expand/collapse.
    """
    if not text:
        return {"text": None}

    return {
        "text": text,
        "limit": limit,
        "uid": uid,
        "is_truncated": len(text) > limit,
        "head": text[:limit],
        "tail": text[limit:],
    }


@register.filter
def join_ids(objects):
    return ", ".join(str(o.id) for o in objects)


def get_field_template_name(field):
    """Determine which template to use for rendering a field wrapper.

    Returns the template path based on the widget type.
    This is for the field wrapper (label + widget + errors), not the widget itself.
    """
    widget = field.field.widget

    # The hedge choice field is an hedge case, because it's a radio select
    # but we must use the normal field template for rendering. All the specific
    # radio code is in the widget template.
    if isinstance(widget, HedgeChoiceField):
        return "django/forms/fields/field.html"
    elif isinstance(widget, CheckboxInput):
        return "django/forms/fields/checkbox.html"
    elif isinstance(widget, RadioSelect):
        return "django/forms/fields/radio.html"
    elif isinstance(widget, CheckboxSelectMultiple):
        return "django/forms/fields/checkbox_multiple.html"
    elif isinstance(widget, FileInput):
        return "django/forms/fields/input_file.html"
    elif isinstance(widget, Select):
        return "django/forms/fields/select.html"
    else:
        return "django/forms/fields/field.html"


@register.simple_tag(takes_context=True)
def render_field(context, field, **kwargs):
    """Render a form field with the appropriate DSFR template.

    Usage:
        {% render_field form.my_field %}

    This replaces the old pattern:
        {% include '_field_snippet.html' with field=form.my_field %}
    """
    template_name = get_field_template_name(field)
    t = get_template(template_name)

    new_context = context.flatten()
    new_context.update(
        {
            "field": field,
            "nest_field_class": kwargs.get("nest_field_class", ""),
        }
    )

    return t.render(new_context)
