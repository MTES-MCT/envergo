from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.users.views import RegisterSuccessView, RegisterView

urlpatterns = [
    path(_("register/"), RegisterView.as_view(), name="register"),
    path(
        _("register-success/"), RegisterSuccessView.as_view(), name="register_success"
    ),
]
