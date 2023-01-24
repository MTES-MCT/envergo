from django.urls import path
from django.urls.conf import include
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.views import (
    Dashboard,
    EvaluationDetail,
    EvaluationSearch,
    RequestEvalWizardReset,
    RequestEvalWizardStep1,
    RequestEvalWizardStep2,
    RequestEvalWizardStep3,
    RequestSuccess,
)

urlpatterns = [
    path("", EvaluationSearch.as_view(), name="evaluation_search"),
    path(
        _("form/"),
        include(
            [
                path("", RequestEvalWizardReset.as_view(), name="request_evaluation"),
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
                    _("step-3/<slug:reference>/"),
                    RequestEvalWizardStep3.as_view(),
                    name="request_eval_wizard_step_3",
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
