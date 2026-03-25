import pytest
from django.http import HttpResponse
from django.test import override_settings

from envergo.decorators.csp import csp_report_only_update, csp_update


def _dummy_view(request):
    return HttpResponse("ok")


FAKE_BASE_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", "https://existing.example"],
    "frame-src": ["'self'"],
}

EXTRAS = {
    "script-src": ["https://tally.so"],
    "frame-src": ["https://tally.so"],
}


@override_settings(SECURE_CSP=FAKE_BASE_CSP)
def test_csp_update_extends_global_policy(rf):
    """Extra sources are appended to the matching global directives."""

    view = csp_update(config=EXTRAS)(_dummy_view)
    response = view(rf.get("/"))

    result = response._csp_config
    assert result["script-src"] == [
        "'self'",
        "'unsafe-inline'",
        "https://existing.example",
        "https://tally.so",
    ]
    assert result["frame-src"] == ["'self'", "https://tally.so"]


@override_settings(SECURE_CSP=FAKE_BASE_CSP)
def test_csp_update_preserves_untouched_directives(rf):
    """Directives not mentioned in extras are left unchanged."""

    view = csp_update(config=EXTRAS)(_dummy_view)
    response = view(rf.get("/"))

    assert response._csp_config["default-src"] == ["'self'"]


@override_settings(SECURE_CSP=FAKE_BASE_CSP)
def test_csp_update_does_not_mutate_global_settings(rf):
    """Each request must get its own copy — never modify the settings dict."""

    original_script_src = list(FAKE_BASE_CSP["script-src"])
    view = csp_update(config=EXTRAS)(_dummy_view)
    view(rf.get("/"))

    assert FAKE_BASE_CSP["script-src"] == original_script_src


@override_settings(SECURE_CSP={})
def test_csp_update_with_empty_base_returns_empty(rf):
    """When the global policy is empty, the result stays empty (no header)."""

    view = csp_update(config=EXTRAS)(_dummy_view)
    response = view(rf.get("/"))

    assert response._csp_config == {}


@override_settings(SECURE_CSP_REPORT_ONLY=FAKE_BASE_CSP)
def test_csp_report_only_update_extends_report_policy(rf):
    """The report-only variant extends SECURE_CSP_REPORT_ONLY."""

    view = csp_report_only_update(config=EXTRAS)(_dummy_view)
    response = view(rf.get("/"))

    result = response._csp_ro_config
    assert "https://tally.so" in result["script-src"]
    assert "https://tally.so" in result["frame-src"]


@override_settings(SECURE_CSP=FAKE_BASE_CSP)
def test_csp_update_adds_new_directive(rf):
    """Extras can introduce a directive absent from the base policy."""

    extras = {"connect-src": ["https://api.example"]}
    view = csp_update(config=extras)(_dummy_view)
    response = view(rf.get("/"))

    assert response._csp_config["connect-src"] == ["https://api.example"]
    assert response._csp_config["default-src"] == ["'self'"]


def test_csp_update_rejects_non_dict():
    """A non-dict config raises TypeError at decoration time."""

    with pytest.raises(TypeError, match="mapping"):
        csp_update(config="bad")
