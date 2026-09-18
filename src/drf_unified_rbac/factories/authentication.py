from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from drf_unified_rbac.conf import get_required_rbac_string


def get_local_auth_adapter():
    """Load a fresh adapter lazily, with no shared credential/request state."""
    from drf_unified_rbac.authentication.adapters import BaseLocalAuthAdapter

    path = get_required_rbac_string("LOCAL_AUTH_ADAPTER")
    try:
        adapter_class = import_string(path)
        if not isinstance(adapter_class, type) or not issubclass(adapter_class, BaseLocalAuthAdapter):
            raise TypeError("Expected a BaseLocalAuthAdapter subclass")
        return adapter_class()
    except Exception as exc:
        raise ImproperlyConfigured(
            f"Unable to construct DRF_RBAC.LOCAL_AUTH_ADAPTER {path!r}; "
            "expected a concrete BaseLocalAuthAdapter subclass with no required constructor arguments"
        ) from exc
