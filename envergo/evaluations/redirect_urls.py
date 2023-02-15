from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/evaluations", permanent=True)),
    path("<path:url>", RedirectView.as_view(url='/evaluations/%(url)s', permanent=True)),
]
