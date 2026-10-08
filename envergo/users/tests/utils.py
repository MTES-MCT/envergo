import time

from django.core import signing


def signed_display_time(seconds_ago):
    """Build a signup form display time, as if the form was shown `seconds_ago`."""
    return signing.dumps(time.time() - seconds_ago)
