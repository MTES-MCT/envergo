from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from envergo.utils.markdown import markdown_to_html


class NewsItem(models.Model):
    """A news item to be displayed on the FAQ page."""

    title = models.CharField(_("Title"), max_length=255)
    content_md = models.TextField(_("Content"))
    content_html = models.TextField(_("Content HTML"))
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("News item")
        verbose_name_plural = _("News items")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.content_html = markdown_to_html(self.content_md)
        super().save(*args, **kwargs)
