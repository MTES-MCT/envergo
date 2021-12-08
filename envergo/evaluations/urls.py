from django.urls import path
from django.urls.conf import include
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.views import (
    Dashboard,
    EvaluationDetail,
    EvaluationSearch,
    RequestEvaluation,
    RequestEvalWizardReset,
    RequestEvalWizardStep1,
    RequestEvalWizardStep2,
    RequestEvalWizardStepFiles,
    RequestEvalWizardSubmit,
    RequestSuccess,
)

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        _("requests/"),
        include(
            [
                path("", RequestEvaluation.as_view(), name="request_evaluation"),
                path(
                    "wizard/",
                    include(
                        [
                            path(
                                "",
                                RequestEvalWizardReset.as_view(),
                                name="request_eval_wizard_reset",
                            ),
                            path(
                                _("step-1/"),
                                RequestEvalWizardStep1.as_view(),
                                name="request_eval_wizard_step_1",
                            ),
                            path(
                                _("step-2/"),
                                RequestEvalWizardStep2.as_view(),
                                name="request_eval_wizard_step_2",
                            ),
                            path(
                                _("step-files/"),
                                RequestEvalWizardStepFiles.as_view(),
                                name="request_eval_wizard_step_files",
                            ),
                            path(
                                _("done/"),
                                RequestEvalWizardSubmit.as_view(),
                                name="request_eval_wizard_submit",
                            ),
                        ]
                    ),
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
