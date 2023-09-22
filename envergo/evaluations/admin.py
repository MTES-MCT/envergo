import logging
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.contrib.postgres.forms import SimpleArrayField
from django.contrib.sites.models import Site
from django.db.models import Prefetch
from django.http import HttpResponseRedirect, QueryDict
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, linebreaks, mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import (
    EVAL_RESULTS,
    Criterion,
    Evaluation,
    RecipientStatus,
    RegulatoryNoticeLog,
    Request,
    RequestFile,
    generate_reference,
)
from envergo.moulinette.forms import MoulinetteForm
from envergo.utils import crisp

logger = logging.getLogger(__name__)


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    contact_emails = SimpleArrayField(
        forms.EmailField(),
        label=_("Urbanism department email address(es)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
    )
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
    result = forms.ChoiceField(
        label=_("Result"),
        choices=[("", "---")] + EVAL_RESULTS,
        required=False,
        help_text=_(
            "If the result can be computed from criterions, this value will be erased."
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        # If a moulinette url is provided, the evaluation result must by set manually
        if "moulinette_url" in cleaned_data and "result" in cleaned_data:
            moulinette_url = cleaned_data.get("moulinette_url")
            result = cleaned_data.get("result")
            if moulinette_url and not result:
                msg = _(
                    "You must provide an evaluation result, since you set a moulinette url."
                )
                self.add_error("result", msg)

            if moulinette_url:
                parsed_url = urlparse(moulinette_url)
                query = QueryDict(parsed_url.query)
                moulinette_form = MoulinetteForm(data=query)
                if not moulinette_form.is_valid():
                    self.add_error(
                        "moulinette_url", _("The moulinette url is invalid.")
                    )
                    for field, errors in moulinette_form.errors.items():
                        for error in errors:
                            self.add_error(
                                "moulinette_url", mark_safe(f"{field} : {error}")
                            )

        # If a moulinette url is NOT provided, a contact info is required
        if "moulinette_url" in cleaned_data and "contact_md" in cleaned_data:
            moulinette_url = cleaned_data.get("moulinette_url")
            contact_md = cleaned_data.get("contact_md")
            if not moulinette_url and not contact_md:
                msg = _("You must provide contact data.")
                self.add_error("contact_md", msg)

        return cleaned_data


class CriterionAdminForm(forms.ModelForm):
    pass


class CriterionInline(admin.StackedInline):
    model = Criterion
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
    class Media:
        css = {
            "all": ["css/project_admin.css"],
        }

    list_display = [
        "reference",
        "created_at",
        "has_moulinette_url",
        "application_number",
        "result",
        "contact_emails",
        "request_link",
    ]
    form = EvaluationAdminForm
    inlines = [CriterionInline]
    autocomplete_fields = ["request"]
    ordering = ["-created_at"]
    search_fields = [
        "reference",
        "application_number",
        "contact_emails",
    ]
    readonly_fields = ["sent_history"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reference",
                    "moulinette_url",
                    "contact_emails",
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
            {"fields": ("result", "details_md", "rr_mention_md")},
        ),
        (
            _("Contact data"),
            {"fields": ("contact_md",)},
        ),
        (
            _("Sent history"),
            {"fields": ("sent_history",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        """Synchronize the references."""
        if obj.request:
            obj.reference = obj.request.reference
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # The evaluation result depends on all the criterions, that's why
        # we have to save them before.
        # If the moulinette_url is set, thought, the result must be set manually.
        evaluation = form.instance
        if not evaluation.moulinette_url and not evaluation.result:
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

    @admin.display(description=_("Url"), boolean=True)
    def has_moulinette_url(self, obj):
        return bool(obj.moulinette_url)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/rappel-reglementaire/",
                self.admin_site.admin_view(self.rappel_reglementaire),
                name="evaluations_evaluation_rr",
            ),
        ]
        return custom_urls + urls

    def rappel_reglementaire(self, request, object_id):
        evaluation = self.get_object(request, unquote(object_id))

        try:
            rr_email = evaluation.get_regulatory_reminder_email(request)
        except Exception as error:  # noqa
            # There was an error generating the email
            url = reverse("admin:evaluations_evaluation_change", args=[object_id])
            response = HttpResponseRedirect(url)
            self.message_user(
                request,
                f"Impossible de générer le rappel réglementaire -> {error}",
                messages.ERROR,
            )
            return response

        moulinette = evaluation.get_moulinette()
        txt_mail_template = (
            f"evaluations/admin/rr_email_{moulinette.loi_sur_leau.result}.txt"
        )
        html_mail_template = (
            f"evaluations/admin/rr_email_{moulinette.loi_sur_leau.result}.html"
        )

        if request.method == "POST":
            rr_email.send()
            # We need to store the message id from the esp, but in local dev or testing,
            # there is no such sing.
            try:
                message_id = rr_email.anymail_status.message_id
                logger.info(f"Envoi avis réglementaire, message id: {message_id}")
            except AttributeError as e:
                logger.warning(f"Impossible de récupérer le message id: {e}")
                message_id = ""
            RegulatoryNoticeLog.objects.create(
                evaluation=evaluation,
                sender=request.user,
                frm=rr_email.from_email,
                to=rr_email.to,
                cc=rr_email.cc,
                bcc=rr_email.bcc,
                subject=rr_email.subject,
                txt_body=rr_email.body,
                html_body=rr_email.alternatives[0][0],
                moulinette_data=moulinette.raw_data,
                moulinette_result=moulinette.result(),
                message_id=message_id,
            )
            url = reverse("eval_admin_short_url", args=[evaluation.reference])
            full_url = request.build_absolute_uri(url)
            crisp.update_contacts_data(
                rr_email.to + rr_email.cc, evaluation.reference, full_url
            )
            self.message_user(request, "Le rappel réglementaire a été envoyé.")
            response = HttpResponseRedirect(url)
        else:
            context = {
                **self.admin_site.each_context(request),
                "title": "Avis réglementaire",
                "subtitle": str(evaluation),
                "object_id": object_id,
                "evaluation": evaluation,
                "email": rr_email,
                "email_html": rr_email.alternatives[0][0],
                "email_txt": rr_email.body,
                "media": self.media,
                "opts": self.opts,
                "txt_mail_template": txt_mail_template,
                "html_mail_template": html_mail_template,
                "github_prefix": "https://github.com/MTES-MCT/envergo/blob/main/envergo/templates/",
            }

            response = TemplateResponse(
                request, "evaluations/admin/rappel_reglementaire.html", context
            )

        return response

    def sent_history(self, obj):
        """Display ESP data about the sent regulatory notices.

        One sent regulatory notice (from the admin) can generate several emails
        because there are several recipients.
        """
        statuses = RecipientStatus.objects.order_by("recipient")
        logs = (
            RegulatoryNoticeLog.objects.filter(evaluation=obj)
            .order_by("-sent_at")
            .select_related("sender")
            .prefetch_related(Prefetch("recipient_statuses", queryset=statuses))
        )

        content = render_to_string(
            "admin/evaluations/sent_history_field.html",
            {
                "evaluation": obj,
                "logs": logs,
            },
        )
        return mark_safe(content)


class ParcelInline(admin.TabularInline):
    model = Request.parcels.through
    autocomplete_fields = ["parcel"]


class RequestFileInline(admin.TabularInline):
    model = RequestFile
    fields = ["file", "name"]
    extra = 0


class RequestAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "contact_emails": admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
            "project_sponsor_emails": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 3}
            ),
        }


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    form = RequestAdminForm
    list_display = [
        "reference",
        "created_at",
        "has_moulinette_url",
        "application_number",
        "user_type",
        "contact_emails",
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
    search_fields = [
        "reference",
        "application_number",
        "contact_emails",
    ]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("reference", "moulinette_url", "summary")}),
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
                    "user_type",
                    "contact_emails",
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

    def save_model(self, request, obj, form, change):
        """Update model with data from moulinette url if provided."""
        params = obj.moulinette_params

        if "created_surface" in params:
            obj.created_surface = params["created_surface"]

        if "existing_surface" in params:
            obj.existing_surface = params["existing_surface"]

        super().save_model(request, obj, form, change)

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

    @admin.display(description="Avis", ordering="evaluation")
    def evaluation_link(self, obj):
        if not obj.evaluation:
            return ""

        eval = obj.evaluation
        eval_admin_url = reverse(
            "admin:evaluations_evaluation_change", args=[eval.reference]
        )
        link = f'<a href="{eval_admin_url}">{obj.evaluation}</a>'
        return mark_safe(link)

    @admin.display(description=_("Url"), boolean=True)
    def has_moulinette_url(self, obj):
        return bool(obj.moulinette_url)

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

    @admin.action(description=_("Create a regulatory notice from this request"))
    def make_evaluation(self, request, queryset):
        """Create an evaluation matching an existing eval request."""

        if queryset.count() > 1:
            error = _("Please, select one and only one request for this action.")
            self.message_user(request, error, level=messages.ERROR)
            return

        req = queryset[0]
        try:
            evaluation = req.create_evaluation()
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
    list_display = ["name", "file", "request"]


class RegulatoryNoticeLogAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "to": admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
            "cc": admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
            "bcc": admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
            "moulinette_data": admin.widgets.AdminTextareaWidget(attrs={"rows": 6}),
            "moulinette_result": admin.widgets.AdminTextareaWidget(attrs={"rows": 6}),
        }


@admin.register(RegulatoryNoticeLog)
class RegulatoryNoticeLogAdmin(admin.ModelAdmin):
    list_display = [
        "sent_at",
        "evaluation",
        "sender",
        "subject",
    ]
    exclude = ["html_body"]
    readonly_fields = ["html_body_link"]
    form = RegulatoryNoticeLogAdminForm

    def has_module_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def html_body_link(self, obj):
        url = reverse("admin:evaluations_regulatorynoticelog_mail_body", args=[obj.pk])
        link = format_html('<a href="{}">Voir le corps du mail</a>', url)
        return link

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/mail-body/",
                self.admin_site.admin_view(self.mail_body),
                name="evaluations_regulatorynoticelog_mail_body",
            ),
        ]
        return custom_urls + urls

    def mail_body(self, request, object_id):
        log = self.get_object(request, unquote(object_id))
        context = {
            **self.admin_site.each_context(request),
            "title": "Événement d'envoi d'avis réglementaire",
            "subtitle": "Détail de l'e-mail envoyé",
            "object_id": object_id,
            "object": log,
            "log": log,
            "html_body": log.html_body,
            "media": self.media,
            "opts": self.opts,
        }

        response = TemplateResponse(
            request, "admin/evaluations/regulatorynoticelogs/mail_body.html", context
        )

        return response
