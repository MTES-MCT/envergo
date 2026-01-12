from django.urls import include, path
from django.views.generic import RedirectView

from envergo.petitions.views import (
    PetitionProjectAcceptInvitation,
    PetitionProjectAutoRedirection,
    PetitionProjectCreate,
    PetitionProjectDetail,
    PetitionProjectHedgeDataExport,
    PetitionProjectInstructorAlternativeEdit,
    PetitionProjectInstructorAlternativeView,
    PetitionProjectInstructorDossierDSView,
    PetitionProjectInstructorMessagerieMarkUnreadView,
    PetitionProjectInstructorMessagerieView,
    PetitionProjectInstructorNotesView,
    PetitionProjectInstructorProcedureView,
    PetitionProjectInstructorRegulationView,
    PetitionProjectInstructorRequestAdditionalInfoView,
    PetitionProjectInstructorView,
    PetitionProjectInvitationToken,
    PetitionProjectList,
    toggle_follow_project,
)

instruction_urlpatterns = [
    path(
        "",
        PetitionProjectInstructorView.as_view(),
        name="petition_project_instructor_view",
    ),
    path(
        "dossier-complet/",
        PetitionProjectInstructorDossierDSView.as_view(),
        name="petition_project_instructor_dossier_complet_view",
    ),
    path(
        "dossier-ds/",
        RedirectView.as_view(
            pattern_name="petition_project_instructor_dossier_complet_view",
            permanent=True,
        ),
    ),
    path(
        "messagerie/",
        PetitionProjectInstructorMessagerieView.as_view(),
        name="petition_project_instructor_messagerie_view",
    ),
    path(
        "messagerie/marquer-nonlu/",
        PetitionProjectInstructorMessagerieMarkUnreadView.as_view(),
        name="petition_project_instructor_messagerie_mark_unread_view",
    ),
    path(
        "notes/",
        PetitionProjectInstructorNotesView.as_view(),
        name="petition_project_instructor_notes_view",
    ),
    path(
        "alternatives/",
        PetitionProjectInstructorAlternativeView.as_view(),
        name="petition_project_instructor_alternative_view",
    ),
    path(
        "alternatives/<int:simulation_id>/<str:action>/",
        PetitionProjectInstructorAlternativeEdit.as_view(),
        name="petition_project_instructor_alternative_edit",
    ),
    path(
        "procedure/",
        PetitionProjectInstructorProcedureView.as_view(),
        name="petition_project_instructor_procedure_view",
    ),
    path(
        "demander-complement/",
        PetitionProjectInstructorRequestAdditionalInfoView.as_view(),
        name="petition_project_instructor_request_info_view",
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
    path(
        "<slug:reference>/suivi/",
        toggle_follow_project,
        name="petition_project_toggle_follow",
    ),
]
