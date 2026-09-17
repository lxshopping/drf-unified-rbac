from drf_unified_rbac.models import RolePermission


class PermissionRepository:
    """Read permission codes granted through enabled roles."""

    def get_permissions_for_roles(self, role_codes: set[str]) -> set[str]:
        if not role_codes:
            return set()

        permission_codes = RolePermission.objects.filter(
            role__code__in=role_codes,
            role__enabled=True,
            permission__enabled=True,
        ).values_list("permission__code", flat=True).distinct()
        return set(permission_codes)
