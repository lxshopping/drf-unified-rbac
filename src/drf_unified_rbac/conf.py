from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULTS: dict[str, Any] = {
    "AUTH_MODE": "local",
}


def get_rbac_setting(name: str) -> Any:
    """Return one DRF_RBAC setting, falling back to component defaults."""
    if name not in DEFAULTS:
        raise ImproperlyConfigured(f"Unknown DRF_RBAC setting: {name}")

    configured = getattr(settings, "DRF_RBAC", {})
    if configured is None:
        configured = {}
    if not isinstance(configured, dict):
        raise ImproperlyConfigured("DRF_RBAC must be a dictionary")

    return configured.get(name, DEFAULTS[name])

