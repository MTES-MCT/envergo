from django import template

from envergo.confs.models import TopBar

register = template.Library()


@register.inclusion_tag("confs/top_bar.html", takes_context=True)
def top_bar(context):

    if "request" not in context:
        return ""

    data = {"is_active": False}

    # Check if the top bar hiding cookie is set
    cookies = context["request"].COOKIES
    if "hide_top_bar" in cookies:
        return data

    # Display the most recent of the top bar messages that is active for the current site
    top_bar = (
        TopBar.objects.filter(is_active=True, site=context["request"].site)
        .order_by("-updated_at")
        .first()
    )
    if top_bar:
        data.update(
            {
                "message": top_bar.message_html,
                "is_active": top_bar.is_active,
            }
        )
    return data
