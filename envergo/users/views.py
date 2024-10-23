from braces.views import AnonymousRequiredMixin, MessageMixin
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.http import urlsafe_base64_decode
from django.views.generic import CreateView, FormView, TemplateView

from envergo.users.forms import NewsletterOptInForm, RegisterForm
from envergo.users.models import User
from envergo.users.tasks import send_account_activation_email


class Register(AnonymousRequiredMixin, CreateView):
    """Allow users to create new accounts."""

    template_name = "registration/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("register_success")

    def form_valid(self, form):
        """Send a connection/confirmation link to the user."""

        response = super().form_valid(form)
        self.object.is_active = False
        self.object.save()

        user_email = form.cleaned_data["email"]
        send_account_activation_email.delay(user_email, self.request.site.domain)
        return response

    def form_invalid(self, form):
        """Handle invalid data provided.

        If the **only** error is that the provided email is already
        associated to an account, instead of displaying a "this user
        already exists" error, we do as if the registration proceeded
        normally and we send a connection link.
        """
        if (
            len(form.errors) == 1
            and len(form["email"].errors) == 1
            and form["email"].errors.as_data()[0].code == "unique"
        ):
            user_email = form.data["email"]
            send_account_activation_email.delay(user_email, self.request.site.domain)
            return HttpResponseRedirect(self.success_url)
        else:
            return super().form_invalid(form)


class RegisterSuccess(AnonymousRequiredMixin, TemplateView):
    """Display success message after register action."""

    template_name = "registration/register_success.html"


class TokenLogin(AnonymousRequiredMixin, MessageMixin, TemplateView):
    """Check token and authenticates user."""

    template_name = "registration/login_error.html"

    def get(self, request, *args, **kwargs):
        uidb64 = kwargs["uidb64"]
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            user = None

        if user:
            token = kwargs["token"]
            if default_token_generator.check_token(user, token):
                is_first_login = user.last_login is None
                login(self.request, user)

                if is_first_login:
                    user.is_active = True
                    user.save()
                    msg = "Vous venez d'activer votre espace EnvErgo. Bienvenue !"
                else:
                    msg = (
                        "Vous êtes maintenant connecté·e. "
                        "Vous pouvez changer votre mot de passe si vous le souhaitez."
                    )

                self.messages.success(msg)
                redirect_url = reverse("password_change")
                return HttpResponseRedirect(redirect_url)

        return super().get(request, *args, **kwargs)


class NewsletterOptIn(FormView):
    form_class = NewsletterOptInForm

    def form_valid(self, form):
        messages.success(
            self.request,
            "Votre inscription a bien été prise en compte.",
        )
        return HttpResponseRedirect(form.cleaned_data["redirect_url"])

    def form_invalid(self, form):
        message = "Nous n'avons pas pu enregistrer votre inscription à la newsletter."
        for field, errors in form.errors.items():
            field_label = form[field].label
            for error in errors:
                message += f"<br/>{field_label} : {error}"
        messages.error(self.request, message)
        return HttpResponseRedirect(
            form.cleaned_data.get("redirect_url", reverse("home"))
        )
