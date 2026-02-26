import pytest


@pytest.fixture(autouse=True)
def _apply_haie_config(request, settings):
    """Auto-apply haie URL config and domain settings for @pytest.mark.haie tests."""
    if not request.node.get_closest_marker("haie"):
        yield
        return

    from django.urls import clear_url_caches, set_urlconf

    settings.ROOT_URLCONF = "config.urls_haie"
    settings.ENVERGO_HAIE_DOMAIN = "testserver"
    settings.ENVERGO_AMENAGEMENT_DOMAIN = "otherserver"
    clear_url_caches()
    set_urlconf(None)

    yield

    # The settings fixture restores ROOT_URLCONF, but we still need
    # to clear URL resolver caches for the restored configuration.
    clear_url_caches()
    set_urlconf(None)
