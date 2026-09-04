from functools import lru_cache

from django.core.exceptions import ImproperlyConfigured

from drf_unified_rbac.conf import get_rbac_setting
from drf_unified_rbac.providers import BaseRoleProvider, LocalRoleProvider


@lru_cache(maxsize=1)
def get_role_provider() -> BaseRoleProvider:
    """Create and reuse the role provider selected by DRF_RBAC.AUTH_MODE."""
    auth_mode = get_rbac_setting("AUTH_MODE")
    if auth_mode == "local":
        return LocalRoleProvider()
    if auth_mode == "sso":
        return SSORoleProvider()
    raise ImproperlyConfigured(f"Unsupported AUTH_MODE: {auth_mode!r}")

