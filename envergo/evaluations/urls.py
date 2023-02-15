from django.urls import path
from django.urls.conf import include
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from envergo.evaluations.views import (
    Dashboard,
    EvaluationDetail,
    EvaluationSearch,
    RequestEvalWizardHome,
    RequestEvalWizardReset,
    RequestEvalWizardStep1,
    RequestEvalWizardStep2,
    RequestEvalWizardStep3,
    RequestEvalWizardStep3Upload,
    RequestSuccess,
)

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        _("form/"),
        include(
            [
                path("", RequestEvalWizardHome.as_view(), name="request_evaluation"),
                path(
                    _("reset/"),
                    RequestEvalWizardReset.as_view(),
                    name="request_eval_wizard_reset",
                ),
                path("étape-1/", RedirectView.as_view(pattern_name="request_eval_wizard_step_1", permanent=True)),
                path(
                    "etape-1/",
                    RequestEvalWizardStep1.as_view(),
                    name="request_eval_wizard_step_1",
                ),
                path("étape-1/", RedirectView.as_view(pattern_name="request_eval_wizard_step_2", permanent=True)),
                path(
                    "etape-2/",
                    RequestEvalWizardStep2.as_view(),
                    name="request_eval_wizard_step_2",
                ),
                path("étape-3/<slug:reference>", RedirectView.as_view(pattern_name="request_eval_wizard_step_3", permanent=True)),
                path(
                    "etape-3/<slug:reference>/",
                    RequestEvalWizardStep3.as_view(),
                    name="request_eval_wizard_step_3",
                ),
                path(
                    "etape-3/<slug:reference>/fichiers/",
                    RequestEvalWizardStep3Upload.as_view(),
                    name="request_eval_wizard_step_3_upload",
                ),
                path(_("success/"), RequestSuccess.as_view(), name="request_success"),
            ]
        ),
    ),
    path(_("dashboard/"), Dashboard.as_view(), name="dashboard"),
    path(
        "<slug:reference>/",
        EvaluationDetail.as_view(),
        name="evaluation_detail",
    ),
]
