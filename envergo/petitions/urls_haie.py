from django.urls import include, path
from django.views.generic import RedirectView

from envergo.petitions.views import (
    PetitionProjectAcceptInvitation,
    PetitionProjectAutoRedirection,
    PetitionProjectCreate,
    PetitionProjectDetail,
    PetitionProjectHedgeDataExport,
    PetitionProjectInstructorDossierDSView,
    PetitionProjectInstructorMessagerieView,
    PetitionProjectInstructorNotesView,
    PetitionProjectInstructorRegulationView,
    PetitionProjectInstructorView,
    PetitionProjectInvitationToken,
    PetitionProjectList,
)

instruction_urlpatterns = [
    path(
        "",
        PetitionProjectInstructorView.as_view(),
        name="petition_project_instructor_view",
    ),
    path(
        "dossier-ds/",
        PetitionProjectInstructorDossierDSView.as_view(),
        name="petition_project_instructor_dossier_ds_view",
    ),
    path(
        "messagerie/",
        PetitionProjectInstructorMessagerieView.as_view(),
        name="petition_project_instructor_messagerie_view",
    ),
    path(
        "notes/",
        PetitionProjectInstructorNotesView.as_view(),
        name="petition_project_instructor_notes_view",
    ),
    path(
        "<slug:regulation>/",
        PetitionProjectInstructorRegulationView.as_view(),
        name="petition_project_instructor_regulation_view",
    ),
]
instruction_urlpatterns_custom_matomo = (instruction_urlpatterns, "matomo-custom")

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
        "+ref_projet+/consultation/haies/",
        RedirectView.as_view(pattern_name="home"),
        name="petition_project_hedges",
    ),
    # This is another "fake" url, only for matomo tracking
    path(
        "+ref_projet+/instruction/haies/",
        RedirectView.as_view(pattern_name="home"),
        name="instructor_view_hedges",
    ),
    # a path that redirects to the petition project detail page without logging the event
    path(
        "<slug:reference>/auto-redirection/",
        PetitionProjectAutoRedirection.as_view(),
        name="petition_project_auto_redirection",
    ),
    # Include instruction patterns
    path(
        "<slug:reference>/instruction/",
        include(instruction_urlpatterns),
    ),
    # Fake matomo instruction patterns, using a namespace
    path(
        "+ref_projet+/instruction/",
        include(instruction_urlpatterns_custom_matomo),
    ),
    path(
        "<slug:reference>/haies.gpkg",
        PetitionProjectHedgeDataExport.as_view(),
        name="petition_project_hedge_data_export",
    ),
    path(
        "<slug:reference>/invitations/",
        PetitionProjectInvitationToken.as_view(),
        name="petition_project_invitation_token",
    ),
    path(
        "<slug:reference>/invitations/<slug:token>/",
        PetitionProjectAcceptInvitation.as_view(),
        name="petition_project_accept_invitation",
    ),
]
