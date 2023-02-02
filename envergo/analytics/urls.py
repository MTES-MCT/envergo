from django.urls import path

from envergo.analytics.views import (
    DisableVisitorCookie,
    Events,
    FeedbackRespond,
    FeedbackSubmit,
)

urlpatterns = [
    path("", FeedbackSubmit.as_view(), name="feedback_submit"),
    path("respond/", FeedbackRespond.as_view(), name="feedback_respond"),
    path(
        "disablecookieview/",
        DisableVisitorCookie.as_view(),
        name="disable_visitor_cookie",
    ),
    path("events", Events.as_view(), name="events"),
]
