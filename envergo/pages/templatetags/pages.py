import random

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from envergo.moulinette.models import MoulinetteConfig

register = template.Library()


def nav_link(route, label, *event_data, aria_current=False):
    url = reverse(route)
    aria_current = 'aria-current="page"' if aria_current else ""

    data_attrs = ""
    if event_data:
        data_attrs = f"""
        data-event-category="{event_data[0]}"
        data-event-action="{event_data[1]}"
        data-event-name="{event_data[2]}"
    """

    return mark_safe(
        f"""<a class="fr-nav__link" href="{url}" {aria_current} {data_attrs}>
            {label}
        </a>"""
    )


@register.simple_tag(takes_context=True)
def menu_item(context, route, label, *event_data, subroutes=[]):
    """Generate html for a main menu item.

    If you pass a list of subroutes, the menu item will be highlighted
    if the current url is any on the main route or subroutes.
    """
    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    aria_current = route == current_route or current_route in subroutes
    return nav_link(route, label, *event_data, aria_current=aria_current)


@register.simple_tag(takes_context=True)
def sidemenu_item(context, route, label):
    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    aria_current = route == current_route
    url = reverse(route)
    sidemenu_class = "fr-sidemenu__item--current" if aria_current else ""
    aria_attr = 'aria-current="page"' if aria_current else ""
    return mark_safe(
        f"""
        <li class="fr-sidemenu__item {sidemenu_class}">
            <a class="fr-sidemenu__link" href="{url}" {aria_attr}>
                {label}
            </a>
        </li>
        """
    )


@register.simple_tag(takes_context=True)
def evalreq_menu(context, *event_data):
    """Generate html for the "Services urbanisme" collapsible menu."""

    link_route = "request_evaluation"
    link_label = "📍 Services urbanisme"
    subroutes = [
        "request_eval_wizard_step_1",
        "request_eval_wizard_step_2",
        "request_eval_wizard_step_3",
        "request_success",
    ]
    return menu_item(context, link_route, link_label, *event_data, subroutes=subroutes)


@register.simple_tag(takes_context=True)
def faq_menu(context):
    """Generate html for the "Faq" collapsible menu."""

    link_route = "faq"
    link_label = "Questions fréquentes"
    subroutes = [
        "faq_loi_sur_leau",
        "faq_natura_2000",
        "faq_eval_env",
    ]
    return menu_item(context, link_route, link_label, subroutes=subroutes)


@register.simple_tag(takes_context=True)
def evaluation_menu(context):
    """Generate html for the "Mes avis réglementaires" collapsible menu."""
    links = (
        ("evaluation_search", "Retrouver un avis", []),
        ("dashboard", "Tableau de bord", []),
    )

    # Other urls that can be reached from the menu
    additional_routes = ["evaluation_detail"]

    return collapsible_menu(
        context, links, "Mes avis réglementaires", "menu-evaluations", additional_routes
    )


@register.simple_tag(takes_context=True)
def project_owner_menu(context, is_slim=False):
    """Generate html for the "Equipes projet" collapsible menu."""
    links = (
        ("geometricians", "Géomètres", ["GeometrePage", "SimulationClick", "Nav"]),
    )

    return collapsible_menu(
        context, links, "Équipes projet", "menu-project-owner", is_slim=is_slim
    )


def collapsible_menu(
    context, links, label, menu_id, additional_routes=None, is_slim=False
):
    if additional_routes is None:
        additional_routes = []

    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""
    links_html = [
        nav_link(url, label, *event_data, aria_current=(url == current_route))
        for url, label, event_data in links
    ]
    # urls for the menu items
    routes = [link[0] for link in links]
    all_routes = routes + additional_routes
    btn_class = (
        "fr-nav__btn"
        if not is_slim
        else "fr-btn fr-btn--icon-right fr-icon-arrow-down-s-line"
    )

    aria_current = 'aria-current="page"' if current_route in all_routes else ""
    unique_id = f"{menu_id}-{random.randint(0, 100)}"
    menu_html = f"""
        <button class="{btn_class}" aria-expanded="false" aria-controls="{unique_id}" {aria_current}>
            {label}
        </button>
        <div class="fr-collapse fr-menu" id="{unique_id}">
          <ul class="fr-menu__list">
            <li>
            {'</li><li>'.join(links_html)}
            </li>
          </ul>
        </div>
    """
    return mark_safe(menu_html)


@register.simple_tag()
def nb_available_depts():
    """Return nb of depts where EnvErgo is available."""

    return MoulinetteConfig.objects.filter(is_activated=True).count()
