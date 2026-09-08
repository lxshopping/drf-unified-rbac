import pytest

from drf_unified_rbac.authentication import SSOUser
from drf_unified_rbac.domain import Principal
from drf_unified_rbac.models import Role, UserRole
from drf_unified_rbac.providers import LocalRoleProvider, SSORoleProvider


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


def test_principal_from_sso_claims_extracts_configured_client_roles():
    claims = {
        "sub": "external-user",
        "preferred_username": "external",
        "resource_access": {
            "my-app": {"roles": ["admin", "operator", "admin"]},
        },
    }

    principal = Principal.from_sso_claims(claims, client_id="my-app")

    assert principal == Principal(
        subject="external-user",
        username="external",
        auth_source="sso",
        role_codes=("admin", "operator"),
    )


def test_principal_from_sso_user_preserves_identity_and_roles():
    user = SSOUser(
        {
            "sub": "external-user",
            "preferred_username": "external",
            "resource_access": {
                "my-app": {"roles": ["admin", "operator"]},
            },
        },
        client_id="my-app",
    )

    assert Principal.from_user(user) == Principal(
        subject="external-user",
        username="external",
        auth_source="sso",
        role_codes=("admin", "operator"),
    )


def test_missing_client_roles_returns_empty_collection():
    principal = Principal.from_sso_claims(
        {"sub": "external-user"},
        client_id="my-app",
    )

    assert principal.role_codes == ()
    assert SSORoleProvider().get_roles(principal) == set()


def test_sso_provider_returns_principal_role_codes():
    principal = Principal(
        subject="external-user",
        username="external",
        auth_source="sso",
        role_codes=("admin", "operator"),
    )

    assert SSORoleProvider().get_roles(principal) == {"admin", "operator"}


def test_sso_provider_rejects_local_principal(user):
    assert SSORoleProvider().get_roles(Principal.from_user(user)) == set()
