from drf_unified_rbac.domain import Principal

from .base import BaseRoleProvider


class SSORoleProvider(BaseRoleProvider):
    """Return client role codes already verified and normalized from the token."""

    def get_roles(self, principal: Principal) -> set[str]:
        if principal.auth_source != "sso":
            return set()
        return set(principal.role_codes)
