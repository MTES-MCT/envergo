from envergo.analytics.models import Event


def log_event(category, event, session_key, **kwargs):
    Event.objects.create(
        category=category, event=event, session_key=session_key, metadata=kwargs
    )
