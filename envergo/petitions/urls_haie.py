from django.urls import path

from envergo.petitions.views import (
    PetitionProjectAutoRedirection,
    PetitionProjectCreate,
    PetitionProjectDetail,
)

urlpatterns = [
    path("", PetitionProjectCreate.as_view(), name="petition_project_create"),
    path(
        "<slug:reference>/consultation/",
        PetitionProjectDetail.as_view(),
        name="petition_project",
    ),
    # a path that redirects to the petition project detail page without logging the event
    path(
        "<slug:reference>/auto-redirection",
        PetitionProjectAutoRedirection.as_view(),
        name="petition_project_auto_redirection",
    ),
]
