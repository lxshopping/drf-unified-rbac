from abc import ABC, abstractmethod

from drf_unified_rbac.domain import Principal


class BaseRoleProvider(ABC):
    """Strategy interface for resolving role codes for a principal."""

    @abstractmethod
    def get_roles(self, principal: Principal) -> set[str]:
        """Return enabled role codes associated with the principal."""
        raise NotImplementedError

