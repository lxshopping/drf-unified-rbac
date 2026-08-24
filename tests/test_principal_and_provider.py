import pytest

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.models import Role, UserRole
from drf_unified_rbac.providers import LocalRoleProvider


pytestmark = pytest.mark.django_db


def test_principal_from_django_user(user):
    principal = Principal.from_user(user)

    assert principal == Principal(
        subject=str(user.pk),
        username="alice",
        auth_source="local",
    )


def test_local_provider_returns_enabled_assigned_roles(user):
    viewer = Role.objects.create(code="demo_viewer", name="Viewer")
    operator = Role.objects.create(code="demo_operator", name="Operator")
    disabled = Role.objects.create(
        code="demo_disabled",
        name="Disabled",
        enabled=False,
    )
    UserRole.objects.bulk_create(
        [
            UserRole(user=user, role=viewer),
            UserRole(user=user, role=operator),
            UserRole(user=user, role=disabled),
        ]
    )

    roles = LocalRoleProvider().get_roles(Principal.from_user(user))

    assert roles == {"demo_viewer", "demo_operator"}


def test_local_provider_rejects_non_local_principal():
    principal = Principal(
        subject="external-user",
        username="external",
        auth_source="oidc",
    )

    assert LocalRoleProvider().get_roles(principal) == set()

