from datetime import date

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import mark_safe
from django.views.generic import FormView, ListView, TemplateView

from envergo.moulinette.models import MoulinetteConfig
from envergo.moulinette.views import MoulinetteMixin
from envergo.pages.models import NewsItem


class HomeView(MoulinetteMixin, FormView):
    template_name = "pages/home.html"


class StatsView(TemplateView):
    template_name = "pages/stats.html"


class LegalMentionsView(TemplateView):
    template_name = "pages/legal_mentions.html"

    def get_context_data(self, **kwargs):
        visitor_id = self.request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")
        context = super().get_context_data(**kwargs)
        context["visitor_id"] = visitor_id
        return context


class Outlinks(TemplateView):
    template_name = "pages/outlinks.html"

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            try:
                links_report, errors_report = self.check_links()
                context["links"] = links_report
                context["errors"] = errors_report
            except Exception as e:
                messages.error(
                    self.request,
                    f"""Impossible de générer le rapport.
                    Allez embêter les devs avec ce message d'erreur (c'est leur job) : {e}
                    """,
                )
        return context

    def check_links(self):
        token = settings.MATOMO_SECURITY_TOKEN
        if not token:
            raise RuntimeError("No matomo token configured")

        today = date.today()
        data_url = f"https://stats.data.gouv.fr/index.php?module=API&format=JSON&idSite=186&period=month&date={today:%Y-%m-%d}&method=Actions.getOutlinks&flat=1&token_auth={token}&filter_limit=100"  # noqa
        data = requests.get(data_url).json()

        links = []
        errors = []
        for datum in data:
            url = datum["url"]
            label = datum["label"]
            try:
                req = requests.head(url)
                links.append({"label": label, "url": url, "status": req.status_code})
            except Exception as e:
                errors.append({"label": label, "url": url, "error": e})

        return links, errors


class AvailabilityInfo(TemplateView):
    """List departments where EnvErgo is available."""

    template_name = "pages/faq/availability_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["configs_available"] = MoulinetteConfig.objects.filter(
            is_activated=True
        ).order_by("department")

        context["configs_soon"] = MoulinetteConfig.objects.filter(
            is_activated=False
        ).order_by("department")

        return context


class NewsView(ListView):
    template_name = "pages/faq/news.html"
    context_object_name = "news_items"

    def get_queryset(self):
        return NewsItem.objects.all().order_by("-created_at")


class NewsFeed(Feed):
    title = "Les actualités d'EnvErgo"
    link = "/foire-aux-questions/envergo-news/feed/"
    description = "Les nouveautés du projet EnvErgo"

    def items(self):
        return NewsItem.objects.order_by("-created_at")[:10]

    def item_title(self, item):
        return date_format(item.created_at, "DATE_FORMAT")

    def item_description(self, item):
        return mark_safe(item.content_html)

    def item_link(self, item):
        base_url = reverse("faq_news")
        item_url = f"{base_url}#news-item-{item.id}"
        return item_url
