from drf_unified_rbac.domain import Principal
from drf_unified_rbac.models import UserRole

from .base import BaseRoleProvider


class LocalRoleProvider(BaseRoleProvider):
    """Resolve enabled roles assigned to a local Django user."""

    def get_roles(self, principal: Principal) -> set[str]:
        if principal.auth_source != "local":
            return set()

        role_codes = UserRole.objects.filter(
            user_id=principal.subject,
            role__enabled=True,
        ).values_list("role__code", flat=True)
        return set(role_codes)

