import logging

import requests
from braces.views import AnonymousRequiredMixin, MessageMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import CreateView, FormView, TemplateView

from envergo.analytics.utils import update_url_with_matomo_params
from envergo.users.forms import NewsletterOptInForm, RegisterForm
from envergo.users.models import User
from envergo.users.tasks import (
    send_account_activation_email,
    send_new_account_notification,
)
from envergo.utils.auth import make_activate_account_url
from envergo.utils.tools import get_site_literal

logger = logging.getLogger(__name__)


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
        activate_url = make_activate_account_url(self.object)
        send_account_activation_email.delay(
            user_email, self.request.site.id, activate_url
        )
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
            existing_user = User.objects.get(email__iexact=user_email)
            activate_url = make_activate_account_url(existing_user)
            send_account_activation_email.delay(
                user_email, self.request.site.id, activate_url
            )
            return HttpResponseRedirect(self.success_url)
        else:
            return super().form_invalid(form)


class RegisterSuccess(AnonymousRequiredMixin, TemplateView):
    """Display success message after register action."""

    template_name = "registration/register_success.html"


class ActivateAccount(AnonymousRequiredMixin, MessageMixin, TemplateView):
    """Check token and authenticates user."""

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
                send_notification = False
                user.is_active = True
                site_literal = get_site_literal(self.request.site)
                if site_literal == "amenagement":
                    user.access_amenagement = True
                elif site_literal == "haie":
                    # send notification only if it is a new account on GUH
                    send_notification = not user.access_haie
                    user.access_haie = True
                user.save()

                messages.success(request, self.get_success_message())

                if send_notification:
                    send_new_account_notification.delay(user.id, self.request.site.id)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("login")

    def get_success_message(self):
        site_literal = get_site_literal(self.request.site)
        messages = {
            "amenagement": """
                <p><strong>Votre identité est confirmée.</strong></p>
                <p>Connectez-vous pour accéder aux services EnvErgo.</p>
            """,
            "haie": """
                <p><strong>Votre identité est confirmée.</strong></p>
                <p>Connectez-vous pour accéder à la liste de vos dossiers.</p>
            """,
        }
        return messages[site_literal]


class LoginView(auth_views.LoginView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["matomo_custom_url"] = update_url_with_matomo_params(
            self.request.build_absolute_uri(reverse("login")), self.request
        )  # remove the next param which can contain secrets or PII
        return context

    def get_default_redirect_url(self):
        """Return the appropriate redirect URL."""

        site_literal = get_site_literal(self.request.site)
        if site_literal == "amenagement":
            url = settings.AMENAGEMENT_LOGIN_REDIRECT_URL
        else:
            url = settings.HAIE_LOGIN_REDIRECT_URL

        return reverse(url)


class NewsletterOptIn(FormView):
    form_class = NewsletterOptInForm
    http_method_names = ["post"]  # js only

    def form_valid(self, form):
        """Send the form data to Brevo API."""
        if not settings.BREVO.get("API_KEY"):
            logger.error(
                "No Brevo API key found in settings for newsletter opt-in",
                extra={"form": form},
            )
            form.add_error(
                None,
                "Le service n'est pas disponible actuellement. Merci de réessayer plus tard.",
            )
            return self.form_invalid(form)

        api_url = f"{settings.BREVO['API_URL']}contacts/doubleOptinConfirmation"
        headers = {
            "Content-Type": "application/json",
            "api-key": settings.BREVO["API_KEY"],
        }

        body = {
            "email": form.cleaned_data["email"],
            "includeListIds": [
                int(
                    settings.BREVO["NEWSLETTER_LISTS"].get(
                        form.cleaned_data["type"],
                        settings.BREVO["NEWSLETTER_LISTS"]["autre"],
                    )
                )
            ],
            "attributes": {
                "TYPE": form.cleaned_data["type"],
                "OPT_IN_NEWSLETTER": True,
            },
            "redirectionUrl": self.request.build_absolute_uri(
                reverse("newsletter_confirmation")
            ),
            "templateId": int(settings.BREVO["NEWSLETTER_DOUBLE_OPT_IN_TEMPLATE_ID"]),
        }

        response = requests.post(api_url, json=body, headers=headers)

        if 200 <= response.status_code < 400:
            res = JsonResponse({"status": "ok"})
        else:
            logger.error(
                "Error while creating/updating contact via Brevo API",
                extra={
                    "response.status_code": response.status_code,
                    "response.text": response.text,
                    "request.url": api_url,
                    "request.body": body,
                },
            )

            form.add_error(
                None,
                "Le service n'est pas disponible actuellement. Merci de réessayer plus tard.",
            )

            res = self.form_invalid(form)

        return res

    def form_invalid(self, form):
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)


class NewsletterDoubleOptInConfirmation(View):
    def get(self, request, *args, **kwargs):
        messages.success(
            request, "Votre inscription à la newsletter Envergo est confirmée !"
        )
        return HttpResponseRedirect(reverse("home"))
