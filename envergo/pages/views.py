from datetime import date

import requests
from django.conf import settings
from django.views.generic import TemplateView


class HomeView(TemplateView):
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
            links_report = self.check_links()
            context["links"] = links_report
        return context

    def check_links(self):
        token = settings.MATOMO_SECURITY_TOKEN
        today = date.today()
        data_url = f"https://stats.data.gouv.fr/index.php?module=API&format=JSON&idSite=186&period=month&date={today:%Y-%m-%d}&method=Actions.getOutlinks&flat=1&token_auth={token}&filter_limit=100"
        data = requests.get(data_url).json()

        links = []
        for datum in data:
            url = datum["url"]
            label = datum["label"]
            req = requests.head(url)
            links.append({"label": label, "url": url, "status": req.status_code})

        return links
