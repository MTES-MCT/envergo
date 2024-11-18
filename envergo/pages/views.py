import logging
from datetime import date, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.syndication.views import Feed
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.template import TemplateDoesNotExist, loader
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import mark_safe
from django.views.decorators.csrf import requires_csrf_token
from django.views.defaults import ERROR_500_TEMPLATE_NAME, ERROR_PAGE_TEMPLATE
from django.views.generic import FormView, ListView, TemplateView

from config.settings.base import GEOMETRICIAN_WEBINAR_FORM_URL
from envergo.geodata.models import Department
from envergo.moulinette.models import ConfigAmenagement, ConfigHaie, MoulinetteHaie
from envergo.moulinette.views import MoulinetteMixin
from envergo.pages.forms import DemarcheSimplifieeForm
from envergo.pages.models import NewsItem

logger = logging.getLogger(__name__)


class HomeAmenagementView(MoulinetteMixin, FormView):
    template_name = "amenagement/pages/home.html"


class HomeHaieView(TemplateView):
    template_name = "haie/pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departments = (
            Department.objects.defer("geometry").select_related("confighaie").all()
        )
        context["departments"] = departments
        context["activated_departments"] = [
            department
            for department in departments
            if department
            and hasattr(department, "confighaie")
            and department.confighaie.is_activated
        ]
        return context

    def post(self, request, *args, **kwargs):
        data = request.POST
        department_id = data.get("department")
        department = None
        if department_id:
            department = (
                Department.objects.select_related("confighaie")
                .defer("geometry")
                .get(id=department_id)
            )

        config = (
            department.confighaie
            if department and hasattr(department, "confighaie")
            else None
        )

        if config and config.is_activated:
            query_params = {"department": department.department}
            return HttpResponseRedirect(
                f"{reverse('triage')}?{urlencode(query_params)}"
            )

        context = self.get_context_data()
        context["department"] = department
        context["config"] = config
        return self.render_to_response(context)


class GeometriciansView(MoulinetteMixin, FormView):
    template_name = "amenagement/pages/geometricians.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["webinar_url"] = GEOMETRICIAN_WEBINAR_FORM_URL
        context["testimonials"] = [
            (
                "Je ne savais pas que la Loi sur l'eau avait un seuil à 1000 m² en cas de présence de zone humide. "
                "J'utilise EnvErgo à chaque fois désormais pour éviter les surprises.",
                "Un géomètre-expert en Loire-Atlantique",
            ),
            (
                "Rien de pire que de devoir redéposer un dossier d'urbanisme. EnvErgo a évité à mon client de "
                "découvrir une fois le permis d'aménager délivré qu'il y avait un dossier Loi sur l'eau à constituer "
                "pour ce lotissement.",
                "Un géomètre-expert en Vendée",
            ),
            (
                "La simplicité d'utilisation du simulateur EnvErgo le rend très adapté en phases de faisabilité et "
                "de planification réglementaire. En outre l'équipe est réactive en cas de questions.",
                "Un géomètre-expert dans l'Aisne",
            ),
        ]

        context["advantages"] = [
            (
                "Sécurisez",
                "Sécurisez les projets de vos clients : évitez les retards, les surcoûts, les annulations et les "
                "contentieux.",
                "images/calendar_light.svg",
                "images/calendar_dark.svg",
            ),
            (
                "Maîtrisez",
                "Maîtrisez les réglementations environnementales applicables aux projets d'aménagement : seuils "
                "d'entrée en procédure, délais, contacts des administrations compétentes, procédures.",
                "images/legal_light.svg",
                "images/legal_dark.svg",
            ),
            (
                "Informez",
                "Renforcez votre capacité de conseil en proposant une information à jour sur les réglementations "
                "environnementales.",
                "images/reputation_light.svg",
                "images/reputation_dark.svg",
            ),
        ]

        context["questions"] = [
            (
                f"{reverse('faq_loi_sur_leau')}#title-savoir_si_mon_projet_est_soumis",
                "Comment déterminer si mon projet est soumis à la Loi sur l’eau ?",
            ),
            (
                f"{reverse('faq_loi_sur_leau')}#title-travaux_avant_reponse",
                "Puis-je commencer les travaux avant d'avoir reçu une réponse de la préfecture ?",
            ),
            (
                reverse("faq_availability_info"),
                "Dans quels départements est disponible EnvErgo ?",
            ),
        ]

        context["properties"] = [
            (
                "Gratuit",
                "images/money_light.svg",
                "images/money_dark.svg",
                "Des piles de pièces de monnaie",
            ),
            (
                "Public",
                "images/school_light.svg",
                "images/school_dark.svg",
                "Un édifice public",
            ),
            (
                "Anonyme",
                "images/avatar_light.svg",
                "images/avatar_dark.svg",
                "Un avatar de personne",
            ),
            (
                "",
                "images/logo_mte.png",
                "images/logo_mte_dark.svg",
                "Le logo du ministère",
            ),
        ]

        return context


class LegalMentionsView(TemplateView):
    template_name = "pages/legal_mentions.html"


class TermsOfServiceView(TemplateView):
    template_name = "pages/terms_of_service.html"


class PrivacyView(TemplateView):
    template_name = "pages/privacy.html"

    def get_context_data(self, **kwargs):
        visitor_id = self.request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")
        context = super().get_context_data(**kwargs)
        context["visitor_id"] = visitor_id
        return context


class Outlinks(TemplateView):
    template_name = "pages/outlinks.html"

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            try:
                links_report, errors_report = self.check_links()
                context["links"] = links_report
                context["errors"] = errors_report
            except Exception as e:
                messages.error(
                    self.request,
                    f"""Impossible de générer le rapport.
                    Allez embêter les devs avec ce message d'erreur (c'est leur job) : {e}
                    """,
                )
        return context

    def check_links(self):
        token = settings.MATOMO_SECURITY_TOKEN
        if not token:
            raise RuntimeError("No matomo token configured")

        today = date.today()
        last_month = today - timedelta(days=30)
        data_url = f"https://stats.data.gouv.fr/index.php?module=API&format=JSON&idSite=186&period=range&date={last_month:%Y-%m-%d},{today:%Y-%m-%d}&method=Actions.getOutlinks&flat=1&token_auth={token}&filter_limit=100"  # noqa
        data = requests.get(data_url).json()

        links = []
        errors = []
        for datum in data:
            url = datum["url"]
            label = datum["label"]
            try:
                req = requests.head(url, timeout=5)
                links.append({"label": label, "url": url, "status": req.status_code})
            except Exception as e:
                errors.append({"label": label, "url": url, "error": e})

        return links, errors


class AvailabilityInfo(TemplateView):
    """List departments where EnvErgo is available."""

    template_name = "pages/faq/availability_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["configs_available"] = ConfigAmenagement.objects.filter(
            is_activated=True
        ).order_by("department")

        context["configs_soon"] = ConfigAmenagement.objects.filter(
            is_activated=False
        ).order_by("department")

        return context


class NewsView(ListView):
    template_name = "pages/faq/news.html"
    context_object_name = "news_items"

    def get_queryset(self):
        return NewsItem.objects.all().order_by("-created_at")


class NewsFeed(Feed):
    title = "Les actualités d'EnvErgo"
    link = "/foire-aux-questions/envergo-news/feed/"
    description = "Les nouveautés du projet EnvErgo"

    def items(self):
        return NewsItem.objects.order_by("-created_at")[:10]

    def item_title(self, item):
        return date_format(item.created_at, "DATE_FORMAT")

    def item_description(self, item):
        return mark_safe(item.content_html)

    def item_link(self, item):
        base_url = reverse("faq_news")
        item_url = f"{base_url}#news-item-{item.id}"
        return item_url


class DemarcheSimplifieeView(FormView):
    form_class = DemarcheSimplifieeForm

    def form_valid(self, form):
        redirect_url = self.pre_fill_demarche_simplifiee(form)

        if not redirect_url:
            res = self.form_invalid(form)
        else:
            res = HttpResponseRedirect(redirect_url)

        return res

    def pre_fill_demarche_simplifiee(self, form):
        """Send a http request to pre-fill a dossier on demarches-simplifiees.fr based on moulinette data.

        Return the url of the created dossier if successful, None otherwise
        """
        moulinette_url = form.cleaned_data["moulinette_url"]
        parsed_url = urlparse(moulinette_url)
        moulinette_data = parse_qs(parsed_url.query)
        # Flatten the dictionary
        for key, value in moulinette_data.items():
            if isinstance(value, list) and len(value) == 1:
                moulinette_data[key] = value[0]
        department = moulinette_data.get("department")  # department is mandatory
        if not department:
            logger.error(
                "Moulinette URL for guichet unique de la haie should always contain a department to "
                "start a demarche simplifiée",
                extra={"moulinette_url": moulinette_url},
            )
            return None

        config = ConfigHaie.objects.get(
            department__department=department
        )  # it should always exist, otherwise the simulator would not be available
        demarche_id = config.demarche_simplifiee_number

        if not demarche_id:
            logger.error(
                "An activated department should always have a demarche_simplifiee_number",
                extra={"haie config": config.id, "department": department},
            )
            return None

        api_url = f"{settings.DEMARCHES_SIMPLIFIEE['API_URL']}demarches/{demarche_id}/dossiers"
        body = {}
        moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
        for field in config.demarche_simplifiee_pre_fill_config:
            if "id" not in field or "value" not in field:
                logger.error(
                    "Invalid pre-fill configuration for a dossier on demarches-simplifiees.fr",
                    extra={"haie config": config.id, "field": field},
                )
                continue

            body[f"champ_{field['id']}"] = self.get_value_from_source(
                moulinette_url,
                moulinette,
                field["value"],
                field.get("mapping", {}),
                config,
            )

        response = requests.post(
            api_url, json=body, headers={"Content-Type": "application/json"}
        )
        redirect_url = None
        if 200 <= response.status_code < 400:
            data = response.json()
            redirect_url = data.get("dossier_url")
        else:
            logger.error(
                "Error while pre-filling a dossier on demarches-simplifiees.fr",
                extra={"response": response},
            )
        return redirect_url

    def get_value_from_source(
        self, moulinette_url, moulinette, source, mapping, config
    ):
        """Get the value to pre-fill a dossier on demarches-simplifiees.fr from a source.

        Available sources are listed by this method : ConfigHaie.get_demarche_simplifiee_value_sources()
        Depending on the source, the value comes from the moulinette data, the moulinette result or the moulinette url.
        Then it will map the value if a mapping is provided.
        """
        if source == "moulinette_url":
            value = moulinette_url
        elif source.endswith(".result"):
            regulation_slug = source[:-7]
            regulation_result = getattr(moulinette, regulation_slug, None)
            if regulation_result is None:
                logger.warning(
                    "Unable to get the regulation result to pre-fill a démarche simplifiée",
                    extra={
                        "regulation_slug": regulation_slug,
                        "moulinette_url": moulinette_url,
                        "haie config": config.id,
                    },
                )
                value = None
            else:
                value = regulation_result.result
        else:
            value = moulinette.catalog.get(source, None)

        if mapping:
            # if the mapping object is not empty but do not contain the value, log an info
            if value not in mapping:
                logger.info(
                    "The value to pre-fill a dossier on demarches-simplifiees.fr is not in the mapping",
                    extra={
                        "source": source,
                        "mapping": mapping,
                        "moulinette_url": moulinette_url,
                        "haie config": config.id,
                    },
                )

        mapped_value = mapping.get(value, value)

        # Handle boolean values as strings 😞
        return {
            True: "true",
            False: "false",
        }.get(mapped_value, mapped_value)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Une erreur technique nous a empêché de créer votre dossier. "
            "Veuillez nous excuser pour ce désagrément.",
        )
        return HttpResponseRedirect(
            form.cleaned_data.get("moulinette_url", reverse("home"))
        )


@requires_csrf_token
def server_error(request, template_name=ERROR_500_TEMPLATE_NAME):
    """
    500 error handler.

    This method override django.views.defaults.server_error to pass a context, and display the right site base template
    Templates: :template:`500.html`
    """
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_500_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return HttpResponseServerError(
            ERROR_PAGE_TEMPLATE % {"title": "Server Error (500)", "details": ""},
        )
    return HttpResponseServerError(
        template.render({"base_template": request.base_template})
    )
