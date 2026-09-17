import pytest

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.models import Permission, Role, RolePermission, UserRole
from drf_unified_rbac.providers import LocalRoleProvider
from drf_unified_rbac.repositories import PermissionRepository
from drf_unified_rbac.services import AuthorizationService


pytestmark = pytest.mark.django_db


def make_service() -> AuthorizationService:
    return AuthorizationService(LocalRoleProvider(), PermissionRepository())


def test_has_permission_is_true_for_granted_permission(user):
    role = Role.objects.create(code="demo_viewer", name="Viewer")
    permission = Permission.objects.create(code="demo.order.view", name="View")
    UserRole.objects.create(user=user, role=role)
    RolePermission.objects.create(role=role, permission=permission)

    service = make_service()
    principal = Principal.from_user(user)

    assert service.get_roles(principal) == {"demo_viewer"}
    assert service.get_permissions(principal) == {"demo.order.view"}
    assert service.has_permission(principal, "demo.order.view") is True


def test_has_permission_is_false_when_user_has_no_role(user):
    assert make_service().has_permission(
        Principal.from_user(user),
        "demo.order.view",
    ) is False


def test_has_permission_is_false_when_role_has_no_permission(user):
    role = Role.objects.create(code="empty_role", name="Empty")
    UserRole.objects.create(user=user, role=role)

    assert make_service().has_permission(
        Principal.from_user(user),
        "demo.order.view",
    ) is False


def test_has_permission_is_false_for_unknown_permission(user):
    role = Role.objects.create(code="demo_viewer", name="Viewer")
    UserRole.objects.create(user=user, role=role)

    assert make_service().has_permission(
        Principal.from_user(user),
        "demo.order.missing",
    ) is False


@pytest.mark.parametrize("disabled_model", ["role", "permission"])
def test_has_permission_is_false_when_grant_path_is_disabled(user, disabled_model):
    role = Role.objects.create(
        code="demo_viewer",
        name="Viewer",
        enabled=disabled_model != "role",
    )
    permission = Permission.objects.create(
        code="demo.order.view",
        name="View",
        enabled=disabled_model != "permission",
    )
    UserRole.objects.create(user=user, role=role)
    RolePermission.objects.create(role=role, permission=permission)

    assert make_service().has_permission(
        Principal.from_user(user),
        "demo.order.view",
    ) is False

