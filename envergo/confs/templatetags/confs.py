from django import template

from envergo.confs.models import TopBar

register = template.Library()


@register.inclusion_tag("confs/top_bar.html", takes_context=True)
def top_bar(context):

    # Check if the top bar hiding cookie is set
    cookies = context["request"].COOKIES
    if "hide_top_bar" in cookies:
        return {"is_active": False}

    # Display the most recent of the top bar messages that is active
    data = {"is_active": False}
    top_bar = TopBar.objects.filter(is_active=True).order_by("-updated_at").first()
    if top_bar:
        data.update(
            {
                "message": top_bar.message_html,
                "is_active": top_bar.is_active,
            }
        )
    return data
