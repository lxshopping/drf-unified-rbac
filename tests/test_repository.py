import pytest

from drf_unified_rbac.models import Permission, Role, RolePermission
from drf_unified_rbac.repositories import PermissionRepository


pytestmark = pytest.mark.django_db


def test_permissions_for_roles_are_merged_deduplicated_and_enabled_only():
    viewer = Role.objects.create(code="demo_viewer", name="Viewer")
    operator = Role.objects.create(code="demo_operator", name="Operator")
    disabled_role = Role.objects.create(
        code="demo_disabled",
        name="Disabled role",
        enabled=False,
    )
    view = Permission.objects.create(code="demo.order.view", name="View")
    create = Permission.objects.create(code="demo.order.create", name="Create")
    disabled_permission = Permission.objects.create(
        code="demo.order.delete",
        name="Delete",
        enabled=False,
    )

    RolePermission.objects.bulk_create(
        [
            RolePermission(role=viewer, permission=view),
            RolePermission(role=operator, permission=view),
            RolePermission(role=operator, permission=create),
            RolePermission(role=operator, permission=disabled_permission),
            RolePermission(role=disabled_role, permission=create),
        ]
    )

    permissions = PermissionRepository().get_permissions_for_roles(
        {"demo_viewer", "demo_operator", "demo_disabled"}
    )

    assert permissions == {"demo.order.view", "demo.order.create"}


def test_permissions_for_no_roles_is_empty():
    assert PermissionRepository().get_permissions_for_roles(set()) == set()


def test_permissions_for_role_without_grants_is_empty():
    Role.objects.create(code="empty_role", name="Empty")

    assert PermissionRepository().get_permissions_for_roles({"empty_role"}) == set()

