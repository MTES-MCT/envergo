from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.users.views import Register, RegisterSuccess, TokenLogin

urlpatterns = [
    path(_("register/"), Register.as_view(), name="register"),
    path(_("register-success/"), RegisterSuccess.as_view(), name="register_success"),
    path(_("login/<uidb64>/<token>/"), TokenLogin.as_view(), name="token_login"),
]
