from django.urls import path

from envergo.analytics.views import DisableVisitorCookie, FeedbackSubmit

urlpatterns = [
    path('', FeedbackSubmit.as_view(), name='feedback_submit'),
    path(
        "disablecookieview/",
        DisableVisitorCookie.as_view(),
        name="disable_visitor_cookie",
    )
]
