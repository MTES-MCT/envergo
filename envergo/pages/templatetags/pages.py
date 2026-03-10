import random
from typing import Literal

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from envergo.moulinette.models import ConfigAmenagement, ConfigHaie
from envergo.moulinette.templatetags.moulinette import display_validity_range

register = template.Library()


def nav_link(url, label, *event_data, aria_current=False, data_testid=None):
    aria_current = 'aria-current="page"' if aria_current else ""

    data_attrs = ""
    if event_data:
        data_attrs = f"""
        data-event-category="{event_data[0]}"
        data-event-action="{event_data[1]}"
        data-event-name="{event_data[2]}"
    """

    test_attribute = ""
    if data_testid:
        test_attribute = f'data-testid="{data_testid}"'

    return mark_safe(
        f"""<a class="fr-nav__link" href="{url}" {aria_current} {data_attrs} {test_attribute}>
            {label}
        </a>"""
    )


@register.simple_tag(takes_context=True)
def menu_item(context, route, label, *event_data, subroutes=[], data_testid=None):
    """Generate html for a main menu item.

    If you pass a list of subroutes, the menu item will be highlighted
    if the current url is any on the main route or subroutes.
    """
    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    aria_current = route == current_route or current_route in subroutes
    return nav_link(
        reverse(route),
        label,
        *event_data,
        aria_current=aria_current,
        data_testid=data_testid,
    )


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
def parametrage_departments_menu(context, is_slim=False):
    """Generate html for the "Paramétrages" collapsible menu.

    Lists all ConfigHaie objects visible to the current user, sorted by
    department then by validity start date.  Each entry shows the department
    name and, when applicable, the validity range as secondary text.
    """

    current_user = context["user"]

    if not current_user.is_authenticated:
        return None

    configs = (
        ConfigHaie.objects.select_related("department")
        .defer("department__geometry")
        .order_by("department__department", "validity_range")
    )

    if not current_user.is_superuser:
        configs = configs.filter(department__in=current_user.departments.all())

    links = (config_menu_link(config) for config in configs)

    return collapsible_menu(
        context,
        links,
        "Paramétrage",
        "menu-settings-departments",
        is_slim=is_slim,
    )


def config_menu_link(config):
    """Build a (url, label, event_data) tuple for a single ConfigHaie.

    Active + currently valid configs get an "ACTIF" badge instead of dates,
    so admins can spot at a glance which config is live.
    """
    url = reverse(
        "confighaie_detail",
        kwargs={
            "department": config.department.department,
            "date_slug": config.date_slug,
        },
    )

    if config.is_activated and config.is_valid_at():
        label = mark_safe(
            f"{config.department} "
            f'<span class="fr-badge fr-badge--sm fr-badge--success">ACTIF</span>'
        )
    else:
        validity_text = display_validity_range(config.validity_range)
        if validity_text:
            label = mark_safe(
                f"{config.department}<br>"
                f'<span class="fr-text--xs">{validity_text}</span>'
            )
        else:
            label = str(config.department)

    return (url, label, [])


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
def nb_available_depts(site: Literal["haie", "amenagement"] = "amenagement"):
    """Return nb of depts where Envergo is available."""
    Config = {"haie": ConfigHaie, "amenagement": ConfigAmenagement}.get(site)
    return Config.objects.filter(is_activated=True).count()


@register.simple_tag(takes_context=True)
def page_tracking_name(context):
    """Return the name of the page for tracking purposes."""
    try:
        view_name = context.request.resolver_match.view_name
    except AttributeError:
        view_name = None

    if view_name == "home":
        return "HomePage"
    elif view_name == "geometricians":
        return "GeometrePage"
    elif view_name == "moulinette_result":
        return "ResultPage"
    else:
        return view_name
