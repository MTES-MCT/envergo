from functools import partial

from envergo.utils.validators import validate_file_type


class AllowedFileTypesMixin:
    """Form mixin that restricts file fields to a set of allowed types.

    Subclasses must set:
        allowed_file_types: {field name: {extension (dot included): set of mime types}}
    """

    allowed_file_types = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, allowed_types in self.allowed_file_types.items():
            if field_name in self.fields:
                field = self.fields[field_name]
                field.widget.attrs["accept"] = ",".join(allowed_types)
                field.validators.append(
                    partial(validate_file_type, allowed_types=allowed_types)
                )
