from textwrap import shorten

from django import forms
from django.contrib import admin

from envergo.confs.models import TopBar


class TopBarAdminForm(forms.ModelForm):
    class Meta:
        model = TopBar
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message_md"].widget.attrs["rows"] = 5


@admin.register(TopBar)
class TopBarAdmin(admin.ModelAdmin):
    list_display = ["message_summary", "is_active", "updated_at"]
    fields = ("message_md", "is_active")
    form = TopBarAdminForm

    def message_summary(self, obj):
        return shorten(obj.message_md, width=50, placeholder="…")
