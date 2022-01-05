from django.views.generic import ListView

from envergo.stats.models import Stat


class StatsView(ListView):
    template_name = "stats/stats.html"
    context_object_name = "stats"
    model = Stat
