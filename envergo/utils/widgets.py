import json

from django import forms


class JSONWidget(forms.Textarea):
    """A widget to prettily display formated JSON in a textarea."""

    def format_value(self, value):
        if value is None:
            return ""
        try:
            # Format the JSON in a readable way
            return json.dumps(json.loads(value), indent=4)
        except (TypeError, ValueError):
            return value
