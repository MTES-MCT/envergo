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
def menu_collapse(context, menu_label, *args):
    """Generate html for a collapsible  menu item."""

    menu_id = "toto"
    try:
        current_route = context.request.resolver_match.url_name
    except AttributeError:
        current_route = ""

    if len(args) % 2 != 0:
        raise ValueError("Provide a list of urls / label pairs")
    urls = args[::2]
    labels = args[1::2]
    links = list(zip(urls, labels))
    links_html = [nav_link(url, label, url == current_route) for url, label in links]

    aria_current = 'aria-current="page"' if current_route in urls else ""
    menu_html = f"""
        <button class="fr-nav__btn" aria-expanded="false" aria-controls="menu-{menu_id}" {aria_current}>
            {menu_label}
        </button>
        <div class="fr-collapse fr-menu" id="menu-{menu_id}">
          <ul class="fr-menu__list">
            <li>
            {'</li><li>'.join(links_html)}
            </li>
          </ul>
        </div>
    """
    return mark_safe(menu_html)
