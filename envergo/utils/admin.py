from django import forms
from django.contrib.postgres.constraints import ExclusionConstraint
from django.db import router
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html_join, mark_safe


class OverlapValidationFormMixin:
    """Form mixin that validates validity_range overlaps with admin links.

    Applied to admin forms for models with ExclusionConstraints on
    validity_range. Instead of letting the DB constraint produce a plain-text
    error, this mixin detects overlaps in clean() and renders clickable admin
    links to the blocking objects.

    The DB-level ExclusionConstraint is kept as a safety net but skipped during
    form validation (_post_clean) to avoid duplicate error messages.

    Subclasses must set:
        overlap_identity_fields: list of field names that define "same object"
        overlap_error_message: str with {links} placeholder
    """

    overlap_identity_fields = []
    overlap_error_message = ""

    def find_overlapping_objects(self):
        """Query for existing objects that overlap the submitted validity range."""

        # Build main filtering queryset
        filters = {
            field: self.cleaned_data.get(field)
            for field in self.overlap_identity_fields
        }
        qs = self.instance.__class__.objects.filter(**filters)

        # Filter queryset to catch overapping ranges
        validity_range = self.cleaned_data.get("validity_range")
        if validity_range:
            # Only keep objects whose range overlaps, or that have no range
            # (no range = always valid, so always conflicts).
            qs = qs.filter(
                Q(validity_range__overlap=validity_range)
                | Q(validity_range__isnull=True)
            )
        # If validity_range is None (always valid), any same-identity object
        # conflicts regardless of its own range — no extra filter needed.

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        return qs

    def clean(self):
        data = super().clean()
        # Bail out early if the form already has errors — identity fields may
        # be missing from cleaned_data, which would cause incorrect queries.
        if self.errors:
            return data

        overlapping = self.find_overlapping_objects()
        if overlapping.exists():
            app = self.instance._meta.app_label
            model_name = self.instance._meta.model_name
            # URLs come from reverse() and display text from trusted model
            # __str__, so mark_safe on the final message is safe.
            links = format_html_join(
                ", ",
                '<a href="{}">{}</a>',
                (
                    (
                        reverse(f"admin:{app}_{model_name}_change", args=[obj.pk]),
                        str(obj),
                    )
                    for obj in overlapping
                ),
            )
            message = mark_safe(self.overlap_error_message.format(links=links))
            raise forms.ValidationError(message)

        return data

    def _post_clean(self):
        """Skip ExclusionConstraints to avoid duplicate overlap errors.

        Django's _post_clean runs even after clean() raises, so without this
        override the ExclusionConstraint would produce a second, plain-text
        error. We replace validate_constraints with a version that only runs
        CheckConstraints (e.g. the non-empty range check).
        """
        original = self.instance.validate_constraints

        def without_exclusion_constraints(exclude=None, using=None):
            using = using or router.db_for_read(type(self.instance))
            errors = {}
            for constraint in self.instance._meta.constraints:
                if isinstance(constraint, ExclusionConstraint):
                    continue
                try:
                    constraint.validate(
                        type(self.instance),
                        self.instance,
                        exclude=exclude,
                        using=using,
                    )
                except forms.ValidationError as e:
                    errors = e.update_error_dict(errors)
            if errors:
                raise forms.ValidationError(errors)

        self.instance.validate_constraints = without_exclusion_constraints
        try:
            super()._post_clean()
        finally:
            self.instance.validate_constraints = original
