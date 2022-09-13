from django.urls import path

from envergo.analytics.views import DisableVisitorCookie

urlpatterns = [
    path('disablecookieview/', DisableVisitorCookie.as_view(), name='disable_visitor_cookie')
]
