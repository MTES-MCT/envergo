from envergo.confs.models import Setting


def get_setting(setting):
    """Get a setting."""
    try:
        value = Setting.objects.get(setting=setting).value
    except Setting.DoesNotExist:
        value = None
    return value
