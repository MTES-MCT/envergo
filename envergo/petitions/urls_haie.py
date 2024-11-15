from django.urls import path

from envergo.petitions.views import PetitionProjectCreate, PetitionProjectDetail

urlpatterns = [
    path("", PetitionProjectCreate.as_view(), name="petition_project_create"),
    path(
        "<slug:reference>",
        PetitionProjectDetail.as_view(),
        name="petition_project",
    ),
]
