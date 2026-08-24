import pytest
from django.db import IntegrityError, transaction

from drf_unified_rbac.models import Permission, Role, RolePermission, UserRole


pytestmark = pytest.mark.django_db


def test_role_code_is_unique():
    Role.objects.create(code="demo_viewer", name="Viewer")

    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(code="demo_viewer", name="Duplicate")


def test_permission_code_is_unique():
    Permission.objects.create(code="demo.order.view", name="View order")

    with pytest.raises(IntegrityError), transaction.atomic():
        Permission.objects.create(code="demo.order.view", name="Duplicate")


def test_user_role_pair_is_unique(user):
    role = Role.objects.create(code="demo_viewer", name="Viewer")
    UserRole.objects.create(user=user, role=role)

    with pytest.raises(IntegrityError), transaction.atomic():
        UserRole.objects.create(user=user, role=role)


def test_role_permission_pair_is_unique():
    role = Role.objects.create(code="demo_viewer", name="Viewer")
    permission = Permission.objects.create(
        code="demo.order.view",
        name="View order",
    )
    RolePermission.objects.create(role=role, permission=permission)

    with pytest.raises(IntegrityError), transaction.atomic():
        RolePermission.objects.create(role=role, permission=permission)

