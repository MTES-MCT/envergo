from django.conf import settings

from envergo.analytics.models import Event


def log_event(category, event, request, **kwargs):

    visitor_id = request.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")

    if visitor_id:
        Event.objects.create(
            category=category, event=event, session_key=visitor_id, metadata=kwargs
        )
