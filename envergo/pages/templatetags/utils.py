from django import template
from django.forms.widgets import CheckboxInput

register = template.Library()


@register.filter
def is_checkbox(field):
    """Is the given field a checkbox input?."""

    return isinstance(field.field.widget, CheckboxInput)


@register.filter
def add_classes(field, classes):
    """Add some classes to the field widget html."""
    css_classes = field.field.widget.attrs.get("class", "").split(" ")
    all_classes = list(set(classes.split(" ")) | set(css_classes))
    return field.as_widget(attrs={"class": " ".join(all_classes)})
