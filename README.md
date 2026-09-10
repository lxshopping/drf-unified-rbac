# drf-unified-rbac

`drf-unified-rbac` is a reusable Django app that provides role-based authorization for Django REST Framework. It supports local Django users and Keycloak access tokens while keeping role-to-permission grants in the same local RBAC tables.

## Architecture

```text
Local Django User ──────────────┐
                               ↓ adapted by Principal.from_user()
Keycloak token → SSOUser ──────┘
Principal
    ↓ role lookup
LocalRoleProvider or SSORoleProvider
    ↓ UserRole or verified Keycloak Client Roles
Role codes
    ↓ permission lookup
PermissionRepository
    ↓ RolePermission → enabled Permission
Permission codes
    ↓ authorization decision
AuthorizationService
    ↓ action enforcement
RBACPermission
    ↓
DRF ViewSet
```

Responsibilities are intentionally separated:

- `LocalRoleProvider` resolves `Principal → enabled role codes` only.
- `SSORoleProvider` returns the client role codes already verified and normalized from the Keycloak token.
- `PermissionRepository` resolves `role codes → enabled permission codes` only.
- `AuthorizationService` coordinates both dependencies and exposes the public authorization API.
- `RBACPermission` adapts a DRF request and ViewSet action to that service.
- `get_role_provider()` is the only place that selects an implementation from `AUTH_MODE`.

All incomplete or missing authorization rules are denied. Disabled roles and disabled permissions never produce an effective grant.

## Installation

Python 3.10 or newer is required.

```bash
pip install -e .
```

For local development:

```bash
pip install -e ".[dev]"
```

## Django settings

Add the reusable app and DRF to the consuming project:

```python
INSTALLED_APPS = [
    # Django apps ...
    "rest_framework",
    "drf_unified_rbac",
]

DRF_RBAC = {
    "AUTH_MODE": "local",
}
```

`AUTH_MODE` defaults to `"local"`. The package rejects `"oidc"` and every other unsupported value with `django.core.exceptions.ImproperlyConfigured`; there is no silent fallback.

The `UserRole.user` relation uses `settings.AUTH_USER_MODEL`, so the component works with Django's default user and normal custom user models.

### Keycloak SSO mode

Install the normal package dependencies, then configure DRF to authenticate bearer tokens and select the SSO role provider:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "drf_unified_rbac.authentication.KeycloakAuthentication",
    ],
}

DRF_RBAC = {
    "AUTH_MODE": "sso",
    "KEYCLOAK_ISSUER": "https://sso.example.com/realms/myrealm",
    "KEYCLOAK_CLIENT_ID": "my-app",
    # Optional; defaults to KEYCLOAK_CLIENT_ID.
    "KEYCLOAK_AUDIENCE": "my-api",
}
```

The authenticator accepts `Authorization: Bearer <access_token>`, obtains the realm JWKS from `{KEYCLOAK_ISSUER}/protocol/openid-connect/certs`, and verifies the RS256 signature plus `exp`, `iss`, and `aud`. It reads roles only from `resource_access[KEYCLOAK_CLIENT_ID].roles`. No client secret is needed for access-token verification, and no Django user is created.

On the Keycloak side, create client roles whose names exactly match local `Role.code` values and assign them to users. The access token must include those roles under the configured client in `resource_access`, and its `aud` claim must contain `KEYCLOAK_AUDIENCE` (or `KEYCLOAK_CLIENT_ID` when the audience setting is omitted). Add/configure the corresponding client-role and audience token mappers when the client scope does not already emit those claims.

## Migration

After installing and adding the app:

```bash
python manage.py migrate
```

The initial migration creates `Permission`, `Role`, `RolePermission`, and `UserRole`. Demo business permissions are not inserted by the reusable app's migration.

## ViewSet usage

Map every protected action to one permission code:

```python
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet

from drf_unified_rbac.permissions import RBACPermission


class DemoOrderViewSet(ViewSet):
    permission_classes = [RBACPermission]
    required_permissions = {
        "list": "demo.order.view",
        "create": "demo.order.create",
        "approve": "demo.order.approve",
    }

    @action(detail=False, methods=["post"])
    def approve(self, request):
        ...
```

An anonymous user, a missing mapping, an unmapped action, an unknown permission code, or a disabled grant path receives a denial.

## Example project

The repository contains an SQLite example under `example_project/`:

```bash
python example_project/manage.py migrate
python example_project/manage.py seed_demo_rbac
python example_project/manage.py createsuperuser
python example_project/manage.py runserver
```

The seed command creates these reusable demo relationships without putting business data in component migrations:

```text
demo_viewer   → demo.order.view
demo_operator → demo.order.view, demo.order.create
demo_approver → demo.order.view, demo.order.approve
demo_admin    → demo.order.view, demo.order.create, demo.order.approve
```

Assign a seeded role to an existing user in the Django shell:

```python
from django.contrib.auth import get_user_model
from drf_unified_rbac.models import Role, UserRole

user = get_user_model().objects.get(username="alice")
role = Role.objects.get(code="demo_operator")
UserRole.objects.get_or_create(user=user, role=role)
```

Available endpoints are:

```text
GET  /api/rbac/me          authenticated identity, roles and permissions
GET  /api/orders/          demo.order.view
POST /api/orders/          demo.order.create
POST /api/orders/approve/  demo.order.approve
```

The example defaults to local `SessionAuthentication` and `BasicAuthentication`. Set `DRF_RBAC_AUTH_MODE=sso`, `KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID`, and optionally `KEYCLOAK_AUDIENCE` in the environment to run it in SSO mode.

### Current user's RBAC information

`GET /api/rbac/me` requires authentication only (`IsAuthenticated`), with no
business permission check. It adapts the authenticated user through `Principal`
and calls `AuthorizationService.get_roles()` / `get_permissions()`, reusing the
configured role provider and `PermissionRepository`. SSO identities need no local
user or primary key. Role and permission arrays are deduplicated and sorted.

```json
{
  "username": "alice",
  "auth_source": "local",
  "roles": ["admin"],
  "permissions": ["demo.order.create", "demo.order.view"]
}
```

Authenticated users without roles receive HTTP 200 with both arrays empty.
Roles without effective grants yield an empty permissions array. Role codes
retain the provider's existing semantics: local roles are enabled assigned
roles; SSO roles come from the configured client's verified token claims.
Permissions always honor the repository's enabled role/permission filters.
Invalid or expired SSO bearer tokens retain the authenticator's HTTP 401 response.

Local mode (use an existing user's username; curl prompts for the password):

```bash
curl -i -u alice http://127.0.0.1:8000/api/rbac/me
```

SSO mode (use access tokens for users with `admin`, `viewer`, or no client role;
role names must match the existing local `Role.code` grants):

```bash
curl -i -H "Authorization: Bearer <access_token>" http://127.0.0.1:8000/api/rbac/me
curl -i -H "Authorization: Bearer invalid-token" http://127.0.0.1:8000/api/rbac/me
```

On Windows PowerShell, use `curl.exe` for these commands. The example seed uses
`demo_admin` / `demo_viewer`, so tokens using those seed grants must use the same
codes. The endpoint introduces no new role mappings or seed data.

## Direct service usage

Business integrations should depend on the service rather than query RBAC tables directly:

```python
from drf_unified_rbac.domain import Principal
from drf_unified_rbac.services import get_authorization_service

principal = Principal.from_user(request.user)
allowed = get_authorization_service().has_permission(
    principal,
    "demo.order.approve",
)
```

Provider and service instances are reused within a process through `functools.lru_cache`. No per-user roles or permissions are cached. Tests can reset construction with:

```python
from drf_unified_rbac.factories import get_role_provider
from drf_unified_rbac.services import get_authorization_service

get_authorization_service.cache_clear()
get_role_provider.cache_clear()
```

## Test

```bash
pytest -q
python example_project/manage.py check
python example_project/manage.py makemigrations --check
```

The test suite covers model constraints, enabled-state filtering, provider and repository behavior, service decisions, factory errors and instance reuse, and DRF default-deny integration.

## Current scope

SSO support is intentionally limited to verification of Keycloak bearer access tokens and extraction of one client's roles. Group mapping, realm roles, composite-role expansion, UserInfo/Admin API calls, user synchronization, login redirects/callbacks, token refresh, object permissions, data scopes, ABAC, Redis, management APIs, frontend code, multi-tenancy, and audit systems are outside this release.
