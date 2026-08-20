from textwrap import shorten

from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from envergo.confs.models import SETTINGS_HELP, HostedFile, Setting, TopBar


class TopBarAdminForm(forms.ModelForm):
    class Meta:
        model = TopBar
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "message_md" in self.fields:
            self.fields["message_md"].widget.attrs["rows"] = 5

    def clean_message_md(self):
        """Join the message in a single line."""
        message_md = self.cleaned_data["message_md"]
        lines = filter(None, message_md.splitlines())
        message_md = " ".join(lines)
        return message_md


@admin.register(TopBar)
class TopBarAdmin(admin.ModelAdmin):
    list_display = ["message_summary", "is_active", "updated_at", "site"]
    fields = ("message_md", "is_active", "site")
    form = TopBarAdminForm

    def message_summary(self, obj):
        return shorten(obj.message_md, width=50, placeholder="…")


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ["setting", "value"]
    fields = ("setting", "value")

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context.update({"settings_help": SETTINGS_HELP})
        return super().render_change_form(request, context, add, change, form_url, obj)


@admin.register(HostedFile)
class HostedFileAdmin(admin.ModelAdmin):
    list_display = ["name", "public_url", "uploaded_by", "created_at"]
    fields = ("file", "name", "description", "public_url")
    readonly_fields = ("public_url",)

    def public_url(self, obj):
        if not obj.file:
            return "-"
        filename = obj.file.name.removeprefix("documents/")
        domain = settings.ENVERGO_AMENAGEMENT_DOMAIN
        url = f"https://{domain}/fichiers/{filename}"
        return format_html(
            '<a href="{}" target="_blank">/fichiers/{}</a>', url, filename
        )

    public_url.short_description = "URL publique"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
