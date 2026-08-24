from django.db import models


class RolePermission(models.Model):
    """Explicit grant of one permission to one role."""

    role = models.ForeignKey(
        "drf_unified_rbac.Role",
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        "drf_unified_rbac.Permission",
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("role", "permission"),
                name="drf_rbac_unique_role_permission",
            )
        ]
        ordering = ("role_id", "permission_id")

    def __str__(self) -> str:
        return f"{self.role.code} -> {self.permission.code}"

