from django.conf import settings
from django.db import models


class UserRole(models.Model):
    """Assignment of a local Django user to a role."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rbac_user_roles",
    )
    role = models.ForeignKey(
        "drf_unified_rbac.Role",
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "role"),
                name="drf_rbac_unique_user_role",
            )
        ]
        ordering = ("user_id", "role_id")

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.role.code}"

