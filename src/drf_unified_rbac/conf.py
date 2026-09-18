from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULTS: dict[str, Any] = {
    "AUTH_MODE": "local",
    "LOCAL_AUTH_ADAPTER": "drf_unified_rbac.authentication.adapters.DjangoLocalAuthAdapter",
    "LOCAL_LOGIN_ENABLED": True,
    "KEYCLOAK_ISSUER": None,
    "KEYCLOAK_CLIENT_ID": None,
    "KEYCLOAK_AUDIENCE": None,
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

    value = configured.get(name, DEFAULTS[name])
    if name == "AUTH_MODE" and value not in ("local", "sso", "hybrid"):
        raise ImproperlyConfigured(f"Unsupported AUTH_MODE: {value!r}")
    if name == "LOCAL_LOGIN_ENABLED" and not isinstance(value, bool):
        raise ImproperlyConfigured("DRF_RBAC.LOCAL_LOGIN_ENABLED must be a boolean")
    if name == "LOCAL_AUTH_ADAPTER" and (
        not isinstance(value, str) or not value.strip() or "." not in value
    ):
        raise ImproperlyConfigured("DRF_RBAC.LOCAL_AUTH_ADAPTER must be a dotted class path")
    return value


def get_required_rbac_string(name: str) -> str:
    """Return a required, non-empty string setting from ``DRF_RBAC``."""
    value = get_rbac_setting(name)
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(
            f"DRF_RBAC.{name} must be a non-empty string"
        )
    return value.strip()
