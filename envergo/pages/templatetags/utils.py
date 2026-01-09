import warnings
from collections.abc import Iterable, Mapping

from bs4 import BeautifulSoup
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
from django.utils.dateparse import parse_datetime
from django.utils.deprecation import RemovedInDjango51Warning
from django.utils.html import urlize as _urlize

register = template.Library()


@register.filter
def has_custom_template(field):
    """Should we use the field's own template.

    This is a hack, since we should always override the field's templates instead
    of defining "field snippets".

    This should be fixed some day.
    """

    return hasattr(field.field.widget, "custom_template")


@register.filter
def is_checkbox(field):
    """Is the given field a checkbox input?."""

    return isinstance(field.field.widget, CheckboxInput)


@register.filter
def is_checkbox_multiple(field):
    """Is the given field a multiple checkbox input?."""

    return isinstance(field.field.widget, CheckboxSelectMultiple)


@register.filter
def is_radio(field):
    """Is the given field a radio select?."""

    return isinstance(field.field.widget, RadioSelect)


@register.filter
def is_select(field):
    """Is the given field a select?."""

    return isinstance(field.field.widget, Select)


@register.filter
def is_input_file(field):
    """Is the given field an input[type=file] widget?."""

    return isinstance(field.field.widget, FileInput)


@register.filter
def add_classes(field, classes):
    """Add some classes to the field widget html."""
    css_classes = field.field.widget.attrs.get("class", "").split(" ")
    all_classes = sorted(list(set(classes.split(" ")) | set(css_classes)))
    all_classes.remove("")  # Prevent unwanted space in class list
    ret = field.as_widget(attrs={"class": " ".join(all_classes)})
    return ret


@register.filter
def compute_input_classes(field):
    """Compute css classes for the field widget html."""
    classes = "fr-input"
    if hasattr(field, "errors") and field.errors:
        classes = classes + " fr-input--error"
    if (
        hasattr(field.field.widget, "input_type")
        and field.field.widget.input_type == "select"
    ):
        classes = classes + " fr-select"

    return add_classes(field, classes)


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
    """Convert URLs in plain text into clickable links."""
    # Remove existing tag a before urlize
    soup = BeautifulSoup(value, "html.parser")
    for a in soup.findAll("a"):
        a.replaceWith(a["href"])
    result = _urlize(str(soup), nofollow=True, autoescape=False)
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
