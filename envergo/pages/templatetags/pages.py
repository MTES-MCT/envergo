from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_item(context, route, label):
    """Generate html for a main menu item."""

    url = reverse(route)
    request = getattr(context, "request", None)
    current_route = request.resolver_match.url_name if request else ""
    aria_current = 'aria-current="page"' if route == current_route else ""
    return mark_safe(
        f"""
        <a
            class="fr-nav__link"
            href="{url}"
            {aria_current}
        >
            {label}
        </a>
        """
    )
