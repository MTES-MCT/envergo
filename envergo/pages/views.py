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
