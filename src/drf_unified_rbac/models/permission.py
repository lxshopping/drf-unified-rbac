from django.db import models


class Permission(models.Model):
    """A globally unique permission that can be granted to roles."""

    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code

