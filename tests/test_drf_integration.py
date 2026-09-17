import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.viewsets import ViewSet

from drf_unified_rbac.models import Permission, Role, RolePermission, UserRole
from drf_unified_rbac.permissions import RBACPermission


pytestmark = pytest.mark.django_db


class DemoOrderViewSet(ViewSet):
    permission_classes = [RBACPermission]
    required_permissions = {
        "list": "demo.order.view",
        "create": "demo.order.create",
        "approve": "demo.order.approve",
    }

    def list(self, request):
        return Response({"orders": []})

    def create(self, request):
        return Response({}, status=status.HTTP_201_CREATED)

    def approve(self, request):
        return Response({"approved": True})

    def unmapped(self, request):
        return Response({"unsafe": True})


class MissingPermissionMapViewSet(ViewSet):
    permission_classes = [RBACPermission]

    def list(self, request):
        return Response({})


class UnknownPermissionViewSet(ViewSet):
    permission_classes = [RBACPermission]
    required_permissions = {"list": "demo.order.missing"}

    def list(self, request):
        return Response({})


@pytest.fixture
def role_users(django_user_model):
    permissions = {
        action: Permission.objects.create(
            code=f"demo.order.{action}",
            name=action.title(),
        )
        for action in ("view", "create", "approve")
    }
    grants = {
        "viewer": {"view"},
        "operator": {"view", "create"},
        "approver": {"view", "approve"},
    }
    users = {}
    for role_name, actions in grants.items():
        role = Role.objects.create(
            code=f"demo_{role_name}",
            name=role_name.title(),
        )
        user = django_user_model.objects.create_user(username=role_name)
        users[role_name] = user
        UserRole.objects.create(user=user, role=role)
        RolePermission.objects.bulk_create(
            [
                RolePermission(role=role, permission=permissions[action])
                for action in actions
            ]
        )
    return users


def call_action(action, method, user=None):
    request = getattr(APIRequestFactory(), method)("/api/orders/")
    if user is not None:
        force_authenticate(request, user=user)
    view = DemoOrderViewSet.as_view({method: action})
    return view(request)


@pytest.mark.parametrize(
    ("role_name", "action", "method", "expected_status"),
    [
        ("viewer", "list", "get", status.HTTP_200_OK),
        ("viewer", "create", "post", status.HTTP_403_FORBIDDEN),
        ("operator", "list", "get", status.HTTP_200_OK),
        ("operator", "create", "post", status.HTTP_201_CREATED),
        ("operator", "approve", "post", status.HTTP_403_FORBIDDEN),
        ("approver", "approve", "post", status.HTTP_200_OK),
    ],
)
def test_viewset_actions_enforce_rbac(
    role_users,
    role_name,
    action,
    method,
    expected_status,
):
    response = call_action(action, method, role_users[role_name])

    assert response.status_code == expected_status


def test_anonymous_request_is_denied():
    assert call_action("list", "get").status_code == status.HTTP_403_FORBIDDEN


def test_unmapped_action_is_denied(role_users):
    response = call_action("unmapped", "post", role_users["operator"])

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_missing_required_permissions_is_denied(role_users):
    request = APIRequestFactory().get("/api/orders/")
    force_authenticate(request, user=role_users["viewer"])
    response = MissingPermissionMapViewSet.as_view({"get": "list"})(request)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unknown_permission_code_is_denied(role_users):
    request = APIRequestFactory().get("/api/orders/")
    force_authenticate(request, user=role_users["viewer"])
    response = UnknownPermissionViewSet.as_view({"get": "list"})(request)

    assert response.status_code == status.HTTP_403_FORBIDDEN
