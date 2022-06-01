from django.conf import settings

from envergo.analytics.models import Event


def log_event(category, event, session, **kwargs):

    visitor_id = session.COOKIES.get(settings.VISITOR_COOKIE_NAME, "")
    Event.objects.create(
        category=category, event=event, session_key=visitor_id, metadata=kwargs
    )
