from types import SimpleNamespace

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.viewsets import ViewSet

import drf_unified_rbac.authentication.keycloak as keycloak_module
from drf_unified_rbac.authentication import KeycloakAuthentication
from drf_unified_rbac.models import Permission, Role, RolePermission
from drf_unified_rbac.permissions import RBACPermission


pytestmark = pytest.mark.django_db


class StaticJWKClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.public_key)


class SSOOrderViewSet(ViewSet):
    authentication_classes = [KeycloakAuthentication]
    permission_classes = [RBACPermission]
    required_permissions = {
        "list": "order.view",
        "approve": "order.approve",
    }

    def list(self, request):
        return Response({"orders": []})

    def approve(self, request):
        return Response({"approved": True})


@pytest.fixture
def sso_role_permissions():
    view_permission = Permission.objects.create(code="order.view", name="View")
    approve_permission = Permission.objects.create(
        code="order.approve",
        name="Approve",
    )
    admin = Role.objects.create(code="admin", name="Admin")
    viewer = Role.objects.create(code="viewer", name="Viewer")
    RolePermission.objects.bulk_create(
        [
            RolePermission(role=admin, permission=view_permission),
            RolePermission(role=admin, permission=approve_permission),
            RolePermission(role=viewer, permission=view_permission),
        ]
    )


@pytest.mark.parametrize(
    ("role_code", "action", "method", "expected_status"),
    [
        ("admin", "list", "get", status.HTTP_200_OK),
        ("admin", "approve", "post", status.HTTP_200_OK),
        ("viewer", "approve", "post", status.HTTP_403_FORBIDDEN),
    ],
)
def test_keycloak_client_role_uses_local_role_permission_mapping(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
    sso_role_permissions,
    role_code,
    action,
    method,
    expected_status,
):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )
    token = make_keycloak_token(
        resource_access={
            keycloak_config["KEYCLOAK_CLIENT_ID"]: {"roles": [role_code]},
        }
    )
    request = getattr(APIRequestFactory(), method)(
        "/api/orders/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    view = SSOOrderViewSet.as_view({method: action})

    with override_settings(DRF_RBAC=keycloak_config):
        response = view(request)

    assert response.status_code == expected_status
