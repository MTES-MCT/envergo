from django.contrib.sites.shortcuts import get_current_site
from django.views.generic import TemplateView


class MultiSiteMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_site = get_current_site(self.request)
        if current_site.name == "Haie":
            context["base_template"] = "base_haie.html"
        else:
            context["base_template"] = "base.html"
        return context


class MultiSiteTemplateView(MultiSiteMixin, TemplateView):
    pass
