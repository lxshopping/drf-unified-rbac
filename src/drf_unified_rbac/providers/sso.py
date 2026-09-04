from drf_unified_rbac.domain import Principal
from drf_unified_rbac.models import UserRole

from .base import BaseRoleProvider


class SSORoleProvider(BaseRoleProvider):
    """Resolve enabled roles assigned to a local Django user."""


    def get_roles(self, principal: Principal):

        claims = principal.claims or {}

        roles = {
            claims.get("resource_access", {}).get("cmdb-app", {}).get("roles", [])
        }
        return roles