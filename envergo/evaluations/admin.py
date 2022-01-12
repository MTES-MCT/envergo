from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.sites.models import Site
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import linebreaks, mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import (
    Criterion,
    Evaluation,
    Request,
    RequestFile,
    generate_reference,
)


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    reference = forms.CharField(
        label=_("Reference"),
        help_text=_("If you select an existing request, this value will be replaced."),
        required=False,
        initial=generate_reference,
        max_length=64,
    )
    application_number = forms.CharField(
        label=_("Application number"),
        required=False,
        help_text=_('A 15 chars value starting with "P"'),
        max_length=64,
    )


class CriterionAdminForm(forms.ModelForm):
    pass


class CriterionInline(admin.StackedInline):
    model = Criterion
    readonly_fields = ["probability"]
    fields = (
        "order",
        "criterion",
        "result",
        "required_action",
        "probability",
        "description_md",
        "map",
        "legend_md",
    )


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "created_at",
        "application_number",
        "result",
        "probability",
        "request_link",
    ]
    form = EvaluationAdminForm
    inlines = [CriterionInline]
    autocomplete_fields = ["request"]
    ordering = ["-created_at"]
    readonly_fields = ["result", "global_probability"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reference",
                    "contact_email",
                    "request",
                    "application_number",
                    "evaluation_file",
                )
            },
        ),
        (
            _("Project data"),
            {
                "fields": (
                    "address",
                    "created_surface",
                    "existing_surface",
                )
            },
        ),
        (
            _("Evaluation report"),
            {"fields": ("result", "global_probability", "details_md")},
        ),
        (
            _("Contact data"),
            {"fields": ("contact_md",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        """Synchronize the references."""
        if obj.request:
            obj.reference = obj.request.reference
        obj.result = obj.compute_result()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # The evaluation result depends on all the criterions, that's why
        # we have to save them before.
        evaluation = form.instance
        evaluation.result = evaluation.compute_result()
        evaluation.save()

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("request")
        return qs

    @admin.display(description=_("Request"), ordering="request")
    def request_link(self, obj):
        if not obj.request:
            return ""

        request = obj.request
        request_admin_url = reverse(
            "admin:evaluations_request_change", args=[request.reference]
        )
        link = f'<a href="{request_admin_url}">{request}</a>'
        return mark_safe(link)

    @admin.display(description=_("Probability"))
    def probability(self, obj):
        return obj.get_global_probability_display()


class ParcelInline(admin.TabularInline):
    model = Request.parcels.through
    autocomplete_fields = ["parcel"]


class RequestFileInline(admin.TabularInline):
    model = RequestFile
    fields = ["file", "name"]
    extra = 0


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "created_at",
        "application_number",
        "contact_email",
        "project_sponsor_phone_number",
        "evaluation_link",
    ]
    readonly_fields = [
        "reference",
        "created_at",
        "summary",
        "parcels",
        "parcels_map",
        "parcels_geojson",
    ]
    inlines = [ParcelInline, RequestFileInline]
    search_fields = ["reference", "application_number"]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("reference", "summary")}),
        (
            _("Project localisation"),
            {"fields": ("address", "parcels", "parcels_map", "parcels_geojson")},
        ),
        (
            _("Project data"),
            {
                "fields": (
                    "application_number",
                    "created_surface",
                    "existing_surface",
                    "project_description",
                    "additional_data",
                )
            },
        ),
        (
            _("Contact info"),
            {
                "fields": (
                    "contact_email",
                    "project_sponsor_emails",
                    "project_sponsor_phone_number",
                    "send_eval_to_sponsor",
                )
            },
        ),
        (_("Meta info"), {"fields": ("created_at",)}),
    )
    exclude = ["parcels"]
    actions = ["make_evaluation"]
    change_form_template = "evaluations/admin/request_change_form.html"

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("evaluation")
            .prefetch_related("parcels")
        )
        return qs

    @admin.display(description=_("Lien vers la carte des parcelles"))
    def parcels_map(self, obj):

        parcel_map_url = obj.get_parcel_map_url()
        link = f"<a href='{parcel_map_url}'>Voir la carte</a>"
        return mark_safe(link)

    @admin.display(description=_("Exporter vers QGis ou autre"))
    def parcels_geojson(self, obj):

        parcel_export_url = obj.get_parcel_geojson_export_url()
        link = f"<a href='{parcel_export_url}'>Télécharger en geojson</a>"
        return mark_safe(link)

    @admin.display(description=_("Evaluation"), ordering="evaluation")
    def evaluation_link(self, obj):
        if not obj.evaluation:
            return ""

        eval = obj.evaluation
        eval_admin_url = reverse(
            "admin:evaluations_evaluation_change", args=[eval.reference]
        )
        link = f'<a href="{eval_admin_url}">{obj.evaluation}</a>'
        return mark_safe(link)

    @admin.display(description=_("Résumé"))
    def summary(self, obj):
        request_url = reverse("admin:evaluations_request_change", args=[obj.id])
        site = Site.objects.get(id=settings.SITE_ID)

        parcel_map_url = obj.get_parcel_map_url()
        summary_body = render_to_string(
            "evaluations/eval_request_notification.txt",
            {
                "request": obj,
                "request_url": f"https://{site.domain}{request_url}",
                "parcel_map_url": f"https://{site.domain}{parcel_map_url}",
            },
        )
        return mark_safe(linebreaks(summary_body))

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        """Override the change form to show a custom action button or not."""

        if obj:
            try:
                obj.evaluation
            except Evaluation.DoesNotExist:
                context["show_make_eval_button"] = True

        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, obj):
        """Handle the custom change form actione"""

        if "_make-evaluation" in request.POST:
            qs = Request.objects.filter(pk=obj.pk)
            self.make_evaluation(request, qs)
            return HttpResponseRedirect(".")
        else:
            return super().response_change(request, obj)

    @admin.action(description=_("Create an evaluation from this request"))
    def make_evaluation(self, request, queryset):
        """Create an evaluation matching an existing eval request."""

        if queryset.count() > 1:
            error = _("Please, select one and only one request for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        req = queryset[0]
        try:
            req.evaluation
        except Evaluation.DoesNotExist:
            # Good, good…
            pass
        else:
            error = _("There already is an evaluation associated with this request.")
            self.message_user(request, error, level=messages.ERROR)
            return

        try:
            evaluation = Evaluation.objects.create(
                reference=req.reference,
                contact_email=req.contact_email,
                request=req,
                application_number=req.application_number,
                address=req.address,
                created_surface=req.created_surface,
                existing_surface=req.existing_surface,
                global_probability=0,
            )
        except Exception as e:
            error = _("There was an error creating your evaluation: %(error)s") % {
                "error": e
            }
            self.message_user(request, error, level=messages.ERROR)
            return

        admin_url = reverse(
            "admin:evaluations_evaluation_change", args=[evaluation.uid]
        )
        msg = _('<a href="%(admin_url)s">The new evaluation has been created.</a>') % {
            "admin_url": admin_url
        }
        self.message_user(request, mark_safe(msg), level=messages.SUCCESS)
        return


@admin.register(RequestFile)
class RequestFileAdmin(admin.ModelAdmin):
    list_display = ["file", "name", "request"]
