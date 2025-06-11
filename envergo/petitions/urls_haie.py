from django.urls import path
from django.views.generic import RedirectView

from envergo.petitions.views import (
    PetitionProjectAutoRedirection,
    PetitionProjectCreate,
    PetitionProjectDetail,
    PetitionProjectHedgeDataExport,
    PetitionProjectInstructorDossierDSView,
    PetitionProjectInstructorView,
    PetitionProjectInvitationToken,
    PetitionProjectList,
)

urlpatterns = [
    path("", PetitionProjectCreate.as_view(), name="petition_project_create"),
    path("liste", PetitionProjectList.as_view(), name="petition_project_list"),
    path(
        "<slug:reference>/consultation/",
        PetitionProjectDetail.as_view(),
        name="petition_project",
    ),
    # This is another "fake" url, only for matomo tracking
    path(
        "+ref_proj+/consultation/haies/",
        RedirectView.as_view(pattern_name="home"),
        name="petition_project_hedges",
    ),
    # This is another "fake" url, only for matomo tracking
    path(
        "+ref_proj+/instruction/haies/",
        RedirectView.as_view(pattern_name="home"),
        name="instructor_view_hedges",
    ),
    # a path that redirects to the petition project detail page without logging the event
    path(
        "<slug:reference>/auto-redirection/",
        PetitionProjectAutoRedirection.as_view(),
        name="petition_project_auto_redirection",
    ),
    path(
        "<slug:reference>/instruction/",
        PetitionProjectInstructorView.as_view(),
        name="petition_project_instructor_view",
    ),
    path(
        "<slug:reference>/instruction/dossier-ds/",
        PetitionProjectInstructorDossierDSView.as_view(),
        name="petition_project_instructor_dossier_ds_view",
    ),
    path(
        "<slug:reference>/haies.gpkg",
        PetitionProjectHedgeDataExport.as_view(),
        name="petition_project_hedge_data_export",
    ),
    path(
        "<slug:reference>/invitation/",
        PetitionProjectInvitationToken.as_view(),
        name="petition_project_invitation_token",
    ),
]
