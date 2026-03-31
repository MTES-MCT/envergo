# Backported from django 6
# https://github.com/django/django/blob/main/django/views/decorators/csp.py#L32

from functools import wraps

from asgiref.sync import iscoroutinefunction
from django.conf import settings


def _make_csp_decorator(config_attr_name, config_attr_value):
    """General CSP override decorator factory."""

    if not isinstance(config_attr_value, dict):
        raise TypeError("CSP config should be a mapping.")

    def decorator(view_func):
        @wraps(view_func)
        async def _wrapped_async_view(request, *args, **kwargs):
            response = await view_func(request, *args, **kwargs)
            setattr(response, config_attr_name, config_attr_value)
            return response

        @wraps(view_func)
        def _wrapped_sync_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            setattr(response, config_attr_name, config_attr_value)
            return response

        if iscoroutinefunction(view_func):
            return _wrapped_async_view
        return _wrapped_sync_view

    return decorator


def csp_override(config):
    """Override the Content-Security-Policy header for a view."""
    return _make_csp_decorator("_csp_config", config)


def csp_report_only_override(config):
    """Override the Content-Security-Policy-Report-Only header for a view."""
    return _make_csp_decorator("_csp_ro_config", config)


# Not part of the Django 6.0 backport — Envergo-specific decorators.
_SETTINGS_FOR_ATTR = {
    "_csp_config": "SECURE_CSP",
    "_csp_ro_config": "SECURE_CSP_REPORT_ONLY",
}


def _extend_csp(base_config, extras):
    """Return a deep copy of base_config with extra sources appended per directive.

    Returns the base as-is when it is empty/falsy so the middleware skips the
    header (preserving the global "no policy" behaviour).
    """

    if not base_config:
        return base_config

    config = {
        k: list(v) if isinstance(v, (list, tuple)) else v
        for k, v in base_config.items()
    }
    for directive, sources in extras.items():
        config.setdefault(directive, []).extend(sources)
    return config


def _make_csp_update_decorator(config_attr_name, extras):
    """CSP update decorator factory.

    Creates a decorator that extends the global CSP policy with additional
    sources for specific directives.  At request time, it reads the base
    policy from Django settings and appends the extras, so the result always
    tracks the current global policy.
    """

    if not isinstance(extras, dict):
        raise TypeError("CSP config should be a mapping.")

    settings_attr = _SETTINGS_FOR_ATTR[config_attr_name]

    def decorator(view_func):
        @wraps(view_func)
        async def _wrapped_async_view(request, *args, **kwargs):
            response = await view_func(request, *args, **kwargs)
            base = getattr(settings, settings_attr, {})
            setattr(response, config_attr_name, _extend_csp(base, extras))
            return response

        @wraps(view_func)
        def _wrapped_sync_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            base = getattr(settings, settings_attr, {})
            setattr(response, config_attr_name, _extend_csp(base, extras))
            return response

        if iscoroutinefunction(view_func):
            return _wrapped_async_view
        return _wrapped_sync_view

    return decorator


def csp_update(config):
    """Extend the Content-Security-Policy header for a view.

    This completes existing csp directives instead of replacing the
    whole csp polity.
    """

    return _make_csp_update_decorator("_csp_config", config)


def csp_report_only_update(config):
    """Extend the Content-Security-Policy-Report-Only header for a view."""

    return _make_csp_update_decorator("_csp_ro_config", config)
