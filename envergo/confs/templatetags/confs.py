from django import template

from envergo.confs.models import TopBar

register = template.Library()


@register.inclusion_tag("confs/top_bar.html")
def top_bar():
    # Display the most recent of the top bar messages that is active
    context = {"is_active": False}
    top_bar = TopBar.objects.filter(is_active=True).order_by("-updated_at").first()
    if top_bar:
        context.update(
            {
                "message": top_bar.message_html,
                "is_active": top_bar.is_active,
            }
        )
    return context
