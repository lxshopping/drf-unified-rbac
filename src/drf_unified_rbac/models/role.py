from django.db import models


class Role(models.Model):
    """A reusable collection of permissions."""

    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    permissions = models.ManyToManyField(
        "drf_unified_rbac.Permission",
        through="drf_unified_rbac.RolePermission",
        related_name="roles",
    )

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code

