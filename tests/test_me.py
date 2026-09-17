from base64 import b64encode
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.urls import include, path
from rest_framework.test import APIClient

import drf_unified_rbac.authentication.keycloak as keycloak_module
from drf_unified_rbac.authentication import KeycloakAuthentication
from drf_unified_rbac.models import Permission, Role, RolePermission, UserRole
from drf_unified_rbac.permissions import RBACPermission
from drf_unified_rbac.views import MeView


pytestmark = pytest.mark.django_db

urlpatterns = [path("api/rbac/", include("drf_unified_rbac.urls"))]


@pytest.fixture
def client(settings, monkeypatch):
    settings.ROOT_URLCONF = __name__

    def unexpected_rbac_check(*args, **kwargs):
        pytest.fail("The me endpoint must not enforce a business permission")

    monkeypatch.setattr(RBACPermission, "has_permission", unexpected_rbac_check)
    return APIClient()


@pytest.fixture
def grants():
    view = Permission.objects.create(code="demo.order.view", name="View")
    create = Permission.objects.create(code="demo.order.create", name="Create")
    disabled = Permission.objects.create(
        code="demo.order.disabled", name="Disabled", enabled=False
    )
    roles = {
        code: Role.objects.create(code=code, name=code, enabled=code != "disabled")
        for code in ("admin", "viewer", "empty", "disabled")
    }
    RolePermission.objects.bulk_create(
        [
            RolePermission(role=roles["admin"], permission=view),
            RolePermission(role=roles["admin"], permission=create),
            RolePermission(role=roles["admin"], permission=disabled),
            RolePermission(role=roles["viewer"], permission=view),
            RolePermission(role=roles["disabled"], permission=create),
        ]
    )
    return roles


@pytest.mark.parametrize(
    ("assigned", "expected_roles", "expected_permissions"),
    [
        (["admin"], ["admin"], ["demo.order.create", "demo.order.view"]),
        ([], [], []),
        (["empty"], ["empty"], []),
        (["disabled"], [], []),
        (
            ["viewer", "admin", "disabled"],
            ["admin", "viewer"],
            ["demo.order.create", "demo.order.view"],
        ),
    ],
    ids=["with-role", "without-role", "no-permission", "disabled-role", "multiple-roles"],
)
def test_local_me(client, user, grants, assigned, expected_roles, expected_permissions):
    for code in assigned:
        UserRole.objects.create(user=user, role=grants[code])
    credentials = b64encode(b"alice:unused").decode("ascii")

    response = client.get("/api/rbac/me", HTTP_AUTHORIZATION=f"Basic {credentials}")

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice",
        "auth_source": "local",
        "roles": expected_roles,
        "permissions": expected_permissions,
    }


def test_local_anonymous_me_is_denied(client):
    # Preserve the existing SessionAuthentication-first DRF behavior.
    assert client.get("/api/rbac/me").status_code == 403


@pytest.fixture
def sso_client(client, settings, monkeypatch, keycloak_config, keycloak_public_key):
    settings.DRF_RBAC = keycloak_config
    monkeypatch.setattr(MeView, "authentication_classes", [KeycloakAuthentication])
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=keycloak_public_key)
        ),
    )
    return client


@pytest.mark.parametrize(
    ("client_roles", "expected_roles", "expected_permissions"),
    [
        (["admin"], ["admin"], ["demo.order.create", "demo.order.view"]),
        (["viewer"], ["viewer"], ["demo.order.view"]),
        ([], [], []),
        (["empty"], ["empty"], []),
        (["disabled"], ["disabled"], []),
        (
            ["viewer", "admin", "admin"],
            ["admin", "viewer"],
            ["demo.order.create", "demo.order.view"],
        ),
    ],
    ids=["admin", "viewer", "no-client-role", "no-permission", "disabled-role", "duplicates"],
)
def test_sso_me(
    sso_client, grants, make_keycloak_token, keycloak_config, django_user_model,
    client_roles, expected_roles, expected_permissions,
):
    token = make_keycloak_token(
        resource_access={
            keycloak_config["KEYCLOAK_CLIENT_ID"]: {"roles": client_roles},
            "other-client": {"roles": ["admin"]},
        },
        realm_access={"roles": ["admin"]},
    )
    response = sso_client.get("/api/rbac/me", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice.sso",
        "auth_source": "sso",
        "roles": expected_roles,
        "permissions": expected_permissions,
    }
    assert not hasattr(response.wsgi_request.user, "pk")
    assert django_user_model.objects.count() == 0


def test_sso_me_without_resource_access_or_username(sso_client, make_keycloak_token):
    token = make_keycloak_token(resource_access=None, preferred_username=None)
    response = sso_client.get("/api/rbac/me", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    assert response.json() == {
        "username": "keycloak-user-123",
        "auth_source": "sso",
        "roles": [],
        "permissions": [],
    }


@pytest.mark.parametrize("invalid", ["malformed", "expired", "signature", "issuer", "audience"])
def test_sso_me_invalid_token_returns_401(sso_client, make_keycloak_token, invalid):
    if invalid == "malformed":
        token = "not-a-jwt"
    elif invalid == "expired":
        token = make_keycloak_token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    elif invalid == "signature":
        token = make_keycloak_token(
            signing_key=rsa.generate_private_key(public_exponent=65537, key_size=2048)
        )
    elif invalid == "issuer":
        token = make_keycloak_token(iss="https://wrong.example.test")
    else:
        token = make_keycloak_token(aud="wrong-audience")

    response = sso_client.get("/api/rbac/me", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid Keycloak access token."}


def test_sso_me_without_token_returns_401(sso_client):
    response = sso_client.get("/api/rbac/me")

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
