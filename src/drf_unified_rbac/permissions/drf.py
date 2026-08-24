from collections.abc import Mapping
from typing import Any

from rest_framework.permissions import BasePermission

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.services import get_authorization_service


class RBACPermission(BasePermission):
    """Enforce a ViewSet action-to-permission mapping with default deny."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.pk is None:
            return False

        action = getattr(view, "action", None)
        required_permissions = getattr(view, "required_permissions", None)
        if not action or not isinstance(required_permissions, Mapping):
            return False

        permission_code = required_permissions.get(action)
        if not isinstance(permission_code, str) or not permission_code.strip():
            return False

        principal = Principal.from_user(user)
        return get_authorization_service().has_permission(
            principal,
            permission_code,
        )
