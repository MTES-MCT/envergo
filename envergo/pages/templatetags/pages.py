from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()


def nav_link(route, label, aria_current=False):
    url = reverse(route)
    aria_current = 'aria-current="page"' if aria_current else ""
    return mark_safe(
        f"""<a class="fr-nav__link" href="{url}" {aria_current}>
            {label}
        </a>"""
    )


@register.simple_tag(takes_context=True)
def menu_item(context, route, label):
    """Generate html for a main menu item."""

    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    aria_current = route == current_route
    return nav_link(route, label, aria_current)


@register.simple_tag(takes_context=True)
def evalreq_menu(context):
    """Generate html for the "Demander une évaluation" collapsible menu."""

    link_route = "request_evaluation"
    link_label = "Demander une évaluation manuelle"

    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    routes = [
        "request_eval_wizard_step_1",
        "request_eval_wizard_step_2",
        "request_eval_wizard_step_3",
        "request_success",
    ]

    aria_current = 'aria-current="page"' if current_route in routes else ""
    return nav_link(link_route, link_label, aria_current)


@register.simple_tag(takes_context=True)
def faq_menu(context):
    """Generate html for the "Faq" collapsible menu."""

    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    links = (
        ("faq_loi_sur_leau", "Loi sur l'eau"),
        ("faq_natura_2000", "Natura 2000"),
        ("faq_eval_env", "Évaluation environnementale"),
    )
    links_html = [nav_link(url, label, url == current_route) for url, label in links]

    # urls for the menu items
    routes = list(dict(links).keys())

    # Other urls that can be reached from the menu
    additional_routes = []
    all_routes = routes + additional_routes

    aria_current = 'aria-current="page"' if current_route in all_routes else ""
    menu_html = f"""
        <button class="fr-nav__btn" aria-expanded="false" aria-controls="menu-faq" {aria_current}>
            Foire aux questions
        </button>
        <div class="fr-collapse fr-menu" id="menu-faq">
          <ul class="fr-menu__list">
            <li>
            {'</li><li>'.join(links_html)}
            </li>
          </ul>
        </div>
    """
    return mark_safe(menu_html)

@register.simple_tag(takes_context=True)
def evaluation_menu(context):
    """Generate html for the "Mes évaluations" collapsible menu."""

    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    links = (
        ("evaluation_search", "Retrouver une évaluation"),
        ("dashboard", "Tableau de bord"),
    )
    links_html = [nav_link(url, label, url == current_route) for url, label in links]

    # urls for the menu items
    routes = list(dict(links).keys())

    # Other urls that can be reached from the menu
    additional_routes = ["evaluation_detail"]
    all_routes = routes + additional_routes

    aria_current = 'aria-current="page"' if current_route in all_routes else ""
    menu_html = f"""
        <button class="fr-nav__btn" aria-expanded="false" aria-controls="menu-evaluations" {aria_current}>
            Mes évaluations
        </button>
        <div class="fr-collapse fr-menu" id="menu-evaluations">
          <ul class="fr-menu__list">
            <li>
            {'</li><li>'.join(links_html)}
            </li>
          </ul>
        </div>
    """
    return mark_safe(menu_html)
