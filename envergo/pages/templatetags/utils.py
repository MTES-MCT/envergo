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
