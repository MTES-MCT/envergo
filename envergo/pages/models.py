from django.contrib.sitemaps import Sitemap
from django.db import models
from django.urls import reverse
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


class AmenagementSitemap(Sitemap):
    changefreq = "monthly"
    priority = 1.0

    def items(self):
        urls = [
            "moulinette_home",
            "home",
            "legal_mentions",
            "terms_of_service",
            "privacy",
            "accessibility",
            "contact_us",
            "faq",
            "faq_loi_sur_leau",
            "faq_natura_2000",
            "faq_eval_env",
            "faq_news",
            "faq_availability_info",
            "geometricians",
        ]
        return urls

    def location(self, item):
        return reverse(item)


class HaieSitemap(Sitemap):
    changefreq = "monthly"
    priority = 1.0

    def items(self):
        urls = [
            "moulinette_home",
            "home",
            "legal_mentions",
            "accessibility",
            "contact_us",
        ]
        return urls

    def location(self, item):
        return reverse(item)
