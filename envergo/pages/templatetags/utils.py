from django import template
from django.forms.widgets import (
    CheckboxInput,
    CheckboxSelectMultiple,
    FileInput,
    RadioSelect,
)

register = template.Library()


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
def is_input_file(field):
    """Is the given field an input[type=file] widget?."""

    return isinstance(field.field.widget, FileInput)


@register.filter
def add_classes(field, classes):
    """Add some classes to the field widget html."""
    css_classes = field.field.widget.attrs.get("class", "").split(" ")
    all_classes = sorted(list(set(classes.split(" ")) | set(css_classes)))
    return field.as_widget(attrs={"class": " ".join(all_classes)})


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
