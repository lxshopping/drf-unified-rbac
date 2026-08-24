from functools import lru_cache

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.factories import get_role_provider
from drf_unified_rbac.providers import BaseRoleProvider
from drf_unified_rbac.repositories import PermissionRepository


class AuthorizationService:
    """Facade coordinating role lookup and permission lookup."""

    def __init__(
        self,
        role_provider: BaseRoleProvider,
        permission_repository: PermissionRepository,
    ) -> None:
        self._role_provider = role_provider
        self._permission_repository = permission_repository

    def get_roles(self, principal: Principal) -> set[str]:
        return self._role_provider.get_roles(principal)

    def get_permissions(self, principal: Principal) -> set[str]:
        roles = self.get_roles(principal)
        return self._permission_repository.get_permissions_for_roles(roles)

    def has_permission(self, principal: Principal, permission_code: str) -> bool:
        if not permission_code:
            return False
        return permission_code in self.get_permissions(principal)


@lru_cache(maxsize=1)
def get_authorization_service() -> AuthorizationService:
    """Build and reuse the process-local authorization service."""
    return AuthorizationService(
        role_provider=get_role_provider(),
        permission_repository=PermissionRepository(),
    )

