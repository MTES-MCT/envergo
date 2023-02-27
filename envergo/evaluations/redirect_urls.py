from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/evaluations", permanent=True)),
    path(
        "<path:url>", RedirectView.as_view(url="/evaluations/%(url)s", permanent=True)
    ),
]
