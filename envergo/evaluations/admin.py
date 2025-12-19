import logging
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.options import TO_FIELD_VAR
from django.contrib.admin.utils import unquote
from django.contrib.postgres.forms import SimpleArrayField
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponseRedirect, QueryDict
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, linebreaks, mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from envergo.analytics.models import Event
from envergo.evaluations.forms import EvaluationFormMixin, EvaluationVersionForm
from envergo.evaluations.models import (
    Evaluation,
    EvaluationVersion,
    RecipientStatus,
    RegulatoryNoticeLog,
    Request,
    RequestFile,
    generate_reference,
)
from envergo.moulinette.utils import get_moulinette_class_from_url
from envergo.utils.fields import NoIdnEmailField

logger = logging.getLogger(__name__)


class EvalAdminFormMixin(EvaluationFormMixin):
    address = forms.CharField(
        label=_("Address"),
        required=False,
        widget=admin.widgets.AdminTextareaWidget(attrs={"rows": 1}),
    )
    send_eval_to_project_owner = forms.BooleanField(
        label="Envoyer directement au porteur de projet",
        required=False,
    )
    urbanism_department_emails = SimpleArrayField(
        NoIdnEmailField(),
        label=_("Urbanism department email address(es)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
    )
    project_owner_emails = SimpleArrayField(
        NoIdnEmailField(),
        label=_("Project owner email(s)"),
        error_messages={"item_invalid": _("The %(nth)s address is invalid:")},
        widget=admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
    )
    application_number = forms.CharField(
        label=_("Application number"),
        required=False,
        help_text=_('A 15 chars value starting with "P"'),
        max_length=64,
    )


class EvaluationAdminForm(EvalAdminFormMixin, forms.ModelForm):
    reference = forms.CharField(
        label=_("Reference"),
        help_text=_("If you select an existing request, this value will be replaced."),
        required=False,
        initial=generate_reference,
        max_length=64,
    )

    def clean(self):
        cleaned_data = super().clean()

        moulinette_url = cleaned_data.get("moulinette_url", None)
        if moulinette_url:
            parsed_url = urlparse(moulinette_url)
            data = QueryDict(parsed_url.query).dict()
            moulinette_data = {"initial": data, "data": data}
            MoulinetteClass = get_moulinette_class_from_url(moulinette_url)
            moulinette = MoulinetteClass(moulinette_data)
            if not moulinette.is_valid():
                self.add_error("moulinette_url", _("The moulinette url is invalid."))
                for field, errors in moulinette.form_errors().items():
                    for error in errors:
                        self.add_error(
                            "moulinette_url", mark_safe(f"{field} : {error}")
                        )

        return cleaned_data


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "created_at",
        "application_number",
        "urbanism_department_emails",
        "nb_emails_sent",
        "nb_versions",
    ]
    form = EvaluationAdminForm
    autocomplete_fields = ["request"]
    ordering = ["-created_at"]
    search_fields = [
        "reference",
        "application_number",
        "urbanism_department_emails",
    ]
    readonly_fields = ["reference", "request", "sent_history", "versions"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reference",
                    "request",
                )
            },
        ),
        (
            _("Project data"),
            {
                "fields": (
                    "address",
                    "application_number",
                    "project_description",
                )
            },
        ),
        (
            _("Contact info"),
            {
                "fields": (
                    "user_type",
                    "urbanism_department_emails",
                    "urbanism_department_phone",
                    "project_owner_emails",
                    "project_owner_phone",
                    "project_owner_company",
                    "send_eval_to_project_owner",
                )
            },
        ),
        (
            "Contenu de l'avis réglementaire",
            {
                "fields": (
                    "moulinette_url",
                    "is_icpe",
                    "display_actions_to_take",
                    "details_md",
                )
            },
        ),
        (
            _("Sent emails"),
            {"fields": ("rr_mention_md", "sent_history")},
        ),
        (
            _("Versions"),
            {"fields": ("versions",)},
        ),
    )

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):

        # Add warning message if the published version is outdated
        latest_version = obj.versions.first()
        published = True
        if not latest_version:
            self.message_user(
                request,
                "Il n'y a pas de version publiée pour cet avis.",
                level=messages.WARNING,
            )
            published = False
        elif not latest_version.published:
            self.message_user(
                request,
                "La dernière version n'est pas publiée.",
                level=messages.WARNING,
            )
            published = False
        elif (
            latest_version.created_at < obj.updated_at
            and latest_version.content != obj.render_content()
        ):
            local_updated_at = localtime(obj.updated_at)
            local_published_at = localtime(latest_version.created_at)
            msg = f"""
                La dernière version enregistrée de cet avis
                ({date_format(local_updated_at, "SHORT_DATETIME_FORMAT")})
                n'a pas encore été publiée. Dernière publication :
                {date_format(local_published_at, "SHORT_DATETIME_FORMAT")}.
            """
            self.message_user(request, msg, level=messages.WARNING)
            published = False

        context["published"] = published
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_model(self, request, obj, form, change):
        """Synchronize the references."""
        if obj.request:
            obj.reference = obj.request.reference
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("request")
            .annotate(
                nb_versions=Count("versions", distinct=True),
                nb_emails_sent=Count("regulatory_notice_logs", distinct=True),
            )
            .prefetch_related(
                Prefetch(
                    "versions",
                    queryset=EvaluationVersion.objects.order_by("-created_at"),
                )
            )
        )
        return qs

    @admin.display(description="Nb. avis publiés", ordering="nb_versions")
    def nb_versions(self, obj):
        return obj.nb_versions

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/email-avis/",
                self.admin_site.admin_view(self.evaluation_email),
                name="evaluations_evaluation_email_avis",
            ),
            path(
                "<path:object_id>/publish/",
                self.admin_site.admin_view(self.publish_view),
                name="evaluations_evaluation_publish",
            ),
        ]
        return custom_urls + urls

    @transaction.atomic()
    def publish_view(self, request, object_id, extra_context=None):
        """Publish a new version of the evaluation."""

        # Stolen code from the "delete_view" method
        app_label = self.opts.app_label
        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        evaluation = self.get_object(request, unquote(object_id), to_field)
        if evaluation is None:
            return self._get_obj_does_not_exist_redirect(request, self.opts, object_id)

        if request.POST:
            # validate form and create new vesion
            form = EvaluationVersionForm(request.POST)
            if form.is_valid():
                message = form.cleaned_data.get("message")
                try:
                    evaluation.unpublish()
                    version = evaluation.create_version(request.user, message)
                    version.save()
                    admin_url = reverse(
                        "admin:evaluations_evaluation_change", args=[evaluation.uid]
                    )
                    msg = "Une nouvelle version de l'avis a été publiée."
                    self.message_user(request, msg, level=messages.SUCCESS)
                    return HttpResponseRedirect(admin_url)
                except Exception as e:
                    error = (
                        "Une erreur est survenue lors de la publication : %(error)s"
                        % {"error": e}
                    )
                    self.message_user(request, error, level=messages.ERROR)

        else:
            has_versions = evaluation.versions.exists()
            initials = {}
            if not has_versions:
                initials["message"] = "Version initiale"
            form = EvaluationVersionForm(initial=initials)

        object_name = str(self.opts.verbose_name)
        context = {
            **self.admin_site.each_context(request),
            "title": "Publier l'avis réglementaire",
            "subtitle": None,
            "object_name": object_name,
            "object": evaluation,
            "opts": self.opts,
            "app_label": app_label,
            "form": form,
            **(extra_context or {}),
        }

        response = TemplateResponse(request, "evaluations/admin/publish.html", context)
        return response

    def evaluation_email(self, request, object_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

        evaluation = self.get_object(request, unquote(object_id))
        evaluation_email = evaluation.get_evaluation_email()

        try:
            eval_email = evaluation_email.get_email(request)
        except Exception as error:  # noqa
            # There was an error generating the email
            url = reverse("admin:evaluations_evaluation_change", args=[object_id])
            response = HttpResponseRedirect(url)
            self.message_user(
                request,
                f"""
                Impossible de générer l'avis réglementaire. Communiquez ce message à l'équipe dev :
                {error}
                """,
                messages.ERROR,
            )
            return response

        moulinette = evaluation.get_moulinette()
        txt_mail_template = f"evaluations/admin/rr_email_{moulinette.result}.txt"
        html_mail_template = f"evaluations/admin/rr_email_{moulinette.result}.html"

        if request.method == "POST":
            # Let's make sure the user doesn't send the same email twice
            latest_log = (
                RegulatoryNoticeLog.objects.filter(evaluation=evaluation)
                .order_by("-sent_at")
                .first()
            )
            if latest_log:
                delta = timezone.now() - latest_log.sent_at
                if delta.seconds < 10:
                    self.message_user(
                        request,
                        """Il s'est écoulé moins de 10 secondes depuis le dernier envoi.
                        L'envoi de l'avis en double a été bloqué.""",
                        messages.WARNING,
                    )
                    url = reverse(
                        "admin:evaluations_evaluation_email_avis", args=[object_id]
                    )
                    return HttpResponseRedirect(url)

            # Override email recipients with the ones from the form
            to = request.POST.getlist("to")
            cc = request.POST.getlist("cc")
            bcc = request.POST.getlist("bcc")
            all = to + cc + bcc
            if len(all) == 0:
                self.message_user(
                    request,
                    "Vous devez spécifier au moins un destinataire.",
                    messages.ERROR,
                )
                url = reverse(
                    "admin:evaluations_evaluation_email_avis", args=[object_id]
                )
                return HttpResponseRedirect(url)

            # our email provider cannot send email without "To" recipients.
            if len(to) == 0:
                to = cc
                cc = list()

            eval_email.to = to
            eval_email.cc = cc
            eval_email.bcc = bcc
            eval_email.send()

            # We need to store the message id from the esp, but in local dev or testing,
            # there is no such sing.
            try:
                message_id = eval_email.anymail_status.message_id
                logger.info(f"Envoi avis réglementaire, message id: {message_id}")
            except AttributeError as e:
                logger.warning(f"Impossible de récupérer le message id: {e}")
                message_id = ""

            # Log the sent email event. We will later tracke events from the ESP
            # and log individual emails statuses for each recipients
            RegulatoryNoticeLog.objects.create(
                evaluation=evaluation,
                sender=request.user,
                frm=eval_email.from_email,
                to=eval_email.to,
                cc=eval_email.cc,
                bcc=eval_email.bcc,
                subject=eval_email.subject,
                txt_body=eval_email.body,
                html_body=eval_email.alternatives[0][0],
                moulinette_data=moulinette.data,
                moulinette_result=moulinette.result_data(),
                message_id=message_id,
            )

            # Log the analytics events
            if evaluation.is_eligible_to_self_declaration():
                metadata = {
                    "request_reference": evaluation.reference,
                    "message_id": message_id,
                }
                Event.objects.create(
                    category="compliance",
                    event="email-send",
                    session_key="admin",
                    metadata=metadata,
                    site=Site.objects.get(
                        domain=settings.ENVERGO_AMENAGEMENT_DOMAIN
                    ),  # Evaluations are only for Aménagement
                )

            self.message_user(request, "Le rappel réglementaire a été envoyé.")
            url = reverse("eval_admin_short_url", args=[evaluation.reference])
            response = HttpResponseRedirect(url)
        else:
            context = {
                **self.admin_site.each_context(request),
                "title": "E-mail d'avis réglementaire",
                "subtitle": eval_email.subject,
                "object_id": object_id,
                "evaluation": evaluation,
                "email": eval_email,
                "email_html": eval_email.alternatives[0][0],
                "email_txt": eval_email.body,
                "media": self.media,
                "opts": self.opts,
                "txt_mail_template": txt_mail_template,
                "html_mail_template": html_mail_template,
                "github_prefix": "https://github.com/MTES-MCT/envergo/blob/main/envergo/templates/",
            }

            response = TemplateResponse(
                request, "evaluations/admin/email_avis.html", context
            )

        return response

    @admin.display(description=_("Sent history"))
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

    @admin.display(description="Nb. emails envoyés")
    def nb_emails_sent(self, obj):
        return obj.nb_emails_sent

    @admin.display(description=_("Versions"))
    def versions(self, obj):
        content = render_to_string(
            "admin/evaluations/versions.html",
            {"evaluation": obj, "versions": obj.versions.all()},
        )
        return mark_safe(content)


class RequestFileInline(admin.TabularInline):
    model = RequestFile
    fields = ["file", "name"]
    extra = 0


class RequestAdminForm(EvalAdminFormMixin, forms.ModelForm):
    pass


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    form = RequestAdminForm
    list_display = [
        "reference",
        "created_at",
        "application_number",
        "user_type",
        "urbanism_department_emails",
        "urbanism_department_phone",
        "project_owner_phone",
        "evaluation_link",
        "submitted",
    ]
    readonly_fields = [
        "reference",
        "created_at",
        "summary",
    ]
    inlines = [RequestFileInline]
    search_fields = [
        "reference",
        "application_number",
        "urbanism_department_emails",
    ]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("reference",)}),
        (
            _("Project data"),
            {
                "fields": (
                    "address",
                    "application_number",
                    "project_description",
                )
            },
        ),
        (
            _("Contact info"),
            {
                "fields": (
                    "user_type",
                    "urbanism_department_emails",
                    "urbanism_department_phone",
                    "project_owner_emails",
                    "project_owner_phone",
                    "send_eval_to_project_owner",
                )
            },
        ),
        (_("Meta info"), {"fields": ("created_at",)}),
    )
    actions = ["make_evaluation"]
    change_form_template = "evaluations/admin/request_change_form.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("evaluation")
        return qs

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

            upload_files_url = reverse(
                "request_eval_wizard_step_3", args=[obj.reference]
            )
            context["upload_files_url"] = request.build_absolute_uri(upload_files_url)

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
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

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
