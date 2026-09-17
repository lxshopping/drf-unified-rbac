# drf-unified-rbac

Reusable Django/DRF authorization for local Django users, Keycloak SSO users,
and both together. Version **0.2.0** adds APIView support, Hybrid role routing,
RBAC administration APIs, and a recoverable bootstrap command.

## Authentication and authorization

The host authenticates local users using its existing login, password, session,
or token implementation. This package does not provide a local login endpoint.
KeycloakAuthentication verifies SSO access tokens and produces a lightweight
SSOUser; it never synchronizes Keycloak users into Django's user table.

```text
Host local authentication -> Django User -> Principal(auth_source="local")
KeycloakAuthentication    -> SSOUser     -> Principal(auth_source="sso")
                                            |
                                   configured role provider
                              local / sso / hybrid (per principal)
                                            |
                               enabled RBAC Role codes
                                            |
                         RolePermission -> enabled Permission codes
                                            |
                       AuthorizationService -> RBACPermission / me
```

Use `Principal.from_user(request.user)` for both identities. Local subject is
`str(user.pk)`; SSO subject is the verified token `sub`. Matching usernames or
subjects never merge the two identities. Missing declarations, unknown sources,
and missing grants deny access. Staff and superuser flags do not bypass RBAC.

## Installation

Requires Python >=3.10. Package dependency ranges remain Django >=3.2,<6.0 and
DRF >=3.11,<4.0; SSO additionally uses joserfc >=1.7,<2.0.

Build a distribution from this repository:

```bash
python -m pip install -e ".[dev,sso]"
python -m pytest -q
python -m build
```

Outputs:

```text
dist/drf_unified_rbac-0.2.0-py3-none-any.whl
dist/drf_unified_rbac-0.2.0.tar.gz
```

Local-only consumers install the wheel:

```bash
python -m pip install ./dist/drf_unified_rbac-0.2.0-py3-none-any.whl
```

SSO and Hybrid consumers install the SSO extra:

```bash
python -m pip install "./dist/drf_unified_rbac-0.2.0-py3-none-any.whl[sso]"
```

The distribution name is `drf-unified-rbac`; its import and Django app name is
`drf_unified_rbac`. The wheel includes migrations and management commands, but
not tests or the example project. The source archive includes both for testing.

## Django integration and auth modes

```python
INSTALLED_APPS = [
    # Existing host apps, including Django auth/contenttypes ...
    "rest_framework",
    "drf_unified_rbac",
]
```

Mount the package in the host URL configuration:

```python
from django.urls import include, path

urlpatterns = [path("api/rbac/", include("drf_unified_rbac.urls"))]
```

Run `python manage.py migrate`. The existing initial migration creates Role,
Permission, RolePermission and UserRole. Version 0.2.0 needs no new schema
migration. UserRole references the host's `AUTH_USER_MODEL`.

| AUTH_MODE | Accepted principal | Role source |
| --- | --- | --- |
| `local` (default) | Local only | UserRole assignments to enabled Roles |
| `sso` | SSO only | Token client roles intersected with enabled database Roles |
| `hybrid` | Local and SSO | Exactly one provider selected by `principal.auth_source` |

A source mismatch yields no roles or permissions. Unsupported mode values raise
`ImproperlyConfigured`. Both individual providers enforce their source checks,
including when called outside HybridRoleProvider. Hybrid routing never reads
HTTP headers and never combines local assignments with SSO roles.

### Local

Keep the host's existing login and DRF authentication classes. For a session host:

```python
DRF_RBAC = {"AUTH_MODE": "local"}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
```

The host provides its normal Django session middleware and CSRF handling.
The package consumes the resulting authenticated user for authorization.

### SSO

```python
DRF_RBAC = {
    "AUTH_MODE": "sso",
    "KEYCLOAK_ISSUER": "https://sso.example.com/realms/ops",
    "KEYCLOAK_CLIENT_ID": "release",
    "KEYCLOAK_AUDIENCE": "release",  # Defaults to client ID when omitted.
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "drf_unified_rbac.authentication.KeycloakAuthentication",
    ],
}
```

KeycloakAuthentication returns `None` when there is no Bearer header. For Bearer
requests it verifies the RS256 signature against the realm JWKS, plus required
`iss`, `aud`, `exp` and `sub`. Invalid tokens fail authentication. Verification
has not been weakened for Hybrid. JWKS lookup uses a five-minute process cache
and can refresh on key rotation.

Only `resource_access[KEYCLOAK_CLIENT_ID].roles` supplies candidate role codes.
For each candidate, an enabled local `Role` with exactly that `code` must exist;
its RolePermission grants to enabled Permissions provide effective permissions.
Realm roles and other clients' roles are not used. Configure Keycloak client-role
and audience mappers as needed. No client secret or Keycloak Admin API is used.

### Hybrid

```python
DRF_RBAC = {
    "AUTH_MODE": "hybrid",
    "KEYCLOAK_ISSUER": "https://sso.example.com/realms/ops",
    "KEYCLOAK_CLIENT_ID": "release",
    "KEYCLOAK_AUDIENCE": "release",
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "drf_unified_rbac.authentication.KeycloakAuthentication",
    ],
}
```

DRF uses the first authenticator that succeeds. With the order above, an active
local session takes precedence over a Bearer token. Session-authenticated unsafe
requests retain DRF's CSRF requirements. The host should choose and document the
credential precedence it intends, and clients should send the selected identity's
credentials.

For host JWT authentication, configure the host class together with
KeycloakAuthentication, for example `HostLocalAuthentication` followed by
`KeycloakAuthentication`, **only with an explicit host authentication-routing
contract**. If both consume `Authorization: Bearer`, listing both classes alone
does not define safe routing. The host must distinguish which authenticator owns
the credential, returning `None` only for credentials outside its scheme or
route, and must fully verify the selected token. Do not catch a failed token
validation and fall back to another identity. This package does not automatically
route two Bearer authenticators or reimplement host authentication.

## APIView and ViewSet usage

APIView declares one permission:

```python
from rest_framework.views import APIView
from drf_unified_rbac.permissions import RBACPermission

class ReleaseOrderDetailView(APIView):
    permission_classes = [RBACPermission]
    required_permission = "release.order.view"
    # Implement the host's get()/other handlers.
```

ViewSet retains the existing action mapping:

```python
from rest_framework.viewsets import ModelViewSet
from drf_unified_rbac.permissions import RBACPermission

class ReleaseOrderViewSet(ModelViewSet):
    permission_classes = [RBACPermission]
    # Supply the host's queryset, serializer_class and approve action.
    required_permissions = {
        "list": "release.order.view",
        "retrieve": "release.order.view",
        "create": "release.order.create",
        "approve": "release.order.approve",
    }
```

A non-blank string `required_permission` takes precedence. Otherwise RBACPermission
looks up `required_permissions[view.action]`. Missing actions, mappings, empty or
non-string codes, invalid principals, and unknown grants deny access. A single
permission applies to every implemented method on that view; use separate views
or action mappings when operations need distinct permissions.

## Unified current-user contract

`GET /api/rbac/me` keeps its original path **without a trailing slash**, URL name
`drf_unified_rbac:me`, and four response fields:

```json
{
  "username": "admin",
  "auth_source": "local",
  "roles": ["release_admin"],
  "permissions": ["release.order.create", "release.order.view"]
}
```

An SSO response has the same structure with `auth_source: "sso"`. Arrays are
unique and sorted. **Roles are effective, enabled RBAC database roles**: unknown
or disabled token roles are excluded. A valid role with no enabled permissions
can appear in `roles` while contributing nothing to `permissions`. Raw token
roles are not exposed. Disabled permissions never appear.

The endpoint requires authentication only, without a business permission. Valid
users with no grants, including an identity outside the configured single-source
mode, receive HTTP 200 with empty arrays. Invalid principal adaptation returns
403. Anonymous/invalid credential responses follow DRF's configured authenticator
order (Keycloak-only uses 401; session-first commonly uses 403).

### Frontend Hybrid flow

```text
Local login button -> host local login API -> keep host credentials -> GET /api/rbac/me
SSO login button   -> Keycloak code flow -> callback/access token -> GET /api/rbac/me
```

After either flow, menus, routes, pages and buttons consume `me.permissions`.
The post-login authorization logic is identical; do not derive permissions from
`auth_source` or usernames. Server-side RBAC remains authoritative. The frontend,
redirect/callback handling and host local login are outside this package.

## RBAC Admin API

The API manages local Role, Permission, RolePermission and Local UserRole data.
It does not manage Keycloak users, passwords, realms or clients. Every endpoint
uses RBACPermission, with no IsAdminUser/staff/superuser bypass. The existing
Django Admin integration remains separate and retains Django's own admin rules.

Paths below are relative to `/api/rbac/admin/` and have trailing slashes:

| Path | Method | Required permission |
| --- | --- | --- |
| `roles/` | GET / POST | `rbac.role.view` / `rbac.role.create` |
| `roles/<id>/` | GET / PATCH / DELETE | `rbac.role.view` / `rbac.role.update` / `rbac.role.delete` |
| `permissions/` | GET / POST | `rbac.permission.view` / `rbac.permission.create` |
| `permissions/<id>/` | GET / PATCH | `rbac.permission.view` / `rbac.permission.update` |
| `roles/<id>/permissions/` | GET / PUT | `rbac.role.view` / `rbac.role.update` |
| `users/` | GET | `rbac.user_role.view` |
| `users/<id>/roles/` | GET / PUT | `rbac.user_role.view` / `rbac.user_role.update` |

Role and Permission representations contain `id`, `code`, `name`, `description`,
`enabled`, `created_at`, `updated_at`. Create requires unique non-blank `code`
and `name`; description and enabled are optional. IDs/timestamps are read-only.
PATCH updates supplied fields. Role DELETE returns 204 and sets `enabled=False`,
preserving relations; PATCH `enabled=True` restores it. Permission DELETE is not
provided; disable with PATCH. Role codes are the SSO mapping keys, so coordinate
any rename with Keycloak configuration.

### Pagination and search

Roles, permissions and users lists always use DRF page-number pagination:

```text
GET /api/rbac/admin/roles/?search=release&page=1&page_size=25
GET /api/rbac/admin/permissions/?search=order
GET /api/rbac/admin/users/?search=alice
```

Default page size is 50; clients may request up to 200. Response shape:

```json
{"count": 1, "next": null, "previous": null, "results": [{"id": 7, "username": "alice", "is_active": true}]}
```

Roles/permissions search `code` and `name`; users search the host's
`USERNAME_FIELD`, the storage field behind Django's `get_username()`. The user
serializer uses only `pk`, `get_username()` and `is_active` when available. No
password, credential or additional profile field is exposed or editable. Custom
user primary keys, including UUID, are supported. Lists have stable ordering.

### Complete relationship replacement

GET and PUT use the same code-set shape:

```json
{"permission_codes": ["release.order.create", "release.order.view"]}
```

```json
{"role_codes": ["release_admin", "release_viewer"]}
```

PUT replaces the full relation set; `[]` clears it. All codes must exist and be
unique; unknown or duplicate codes return 400 without changing old relations.
Missing target objects return 404. Validation, deletion and insertion are inside
one transaction; the parent role/user is locked on databases supporting row
locks. SQLite uses its own write locking rather than SELECT FOR UPDATE semantics.

Admin relationship GET returns stored assignments, including disabled objects,
so administrators can inspect and repair configuration. Effective authorization
and `/me` always filter disabled roles/permissions. No per-user grant cache delays
changes.

## Bootstrap and recovery

```bash
python manage.py rbac_bootstrap_admin
python manage.py rbac_bootstrap_admin --username admin
```

The command creates/restores all nine built-in permissions listed above, ensures
they are enabled, ensures `rbac_admin` exists and is enabled, and restores every
built-in RolePermission relation. Repeated runs do not duplicate rows. Existing
names and additional custom grants are preserved. The command is transactional.

`--username` optionally binds the role to an existing host user, looking up the
host's `USERNAME_FIELD`. It never creates a user or password. Unknown usernames
produce CommandError without partial bootstrap changes. Use the host's existing
account provisioning first.

For SSO, run bootstrap without a username and create/assign a client role named
`rbac_admin` in the configured Keycloak client. The token should contain:

```json
{"resource_access": {"release": {"roles": ["rbac_admin"]}}}
```

That role maps to the enabled database `rbac_admin` role. The command makes no
Keycloak Admin API calls. Its explicit purpose includes restoring disabled
built-in administration grants.

## Service and cache contract

```python
from drf_unified_rbac.domain import Principal
from drf_unified_rbac.services import get_authorization_service

principal = Principal.from_user(request.user)
service = get_authorization_service()
roles = service.get_roles(principal)
permissions = service.get_permissions(principal)
allowed = service.has_permission(principal, "release.order.view")
```

The service API is unchanged. Factories reuse provider/service instances through
`lru_cache`; HybridRoleProvider routes on every call. Roles and permissions are
queried fresh. After overriding settings in tests or explicitly reloading settings:

```python
from drf_unified_rbac.services import clear_rbac_caches
clear_rbac_caches()
```

Individual `get_authorization_service.cache_clear()` and
`get_role_provider.cache_clear()` remain available; clear both together when
changing AUTH_MODE. Do not rebuild the service on every request.

## Example and validation

```bash
python example_project/manage.py migrate
python example_project/manage.py seed_demo_rbac
python example_project/manage.py createsuperuser
python example_project/manage.py rbac_bootstrap_admin --username admin
python example_project/manage.py runserver
```

The example's Local mode retains SessionAuthentication and BasicAuthentication.
Set `DRF_RBAC_AUTH_MODE` to `sso` or `hybrid` and configure
`DRF_RBAC_KEYCLOAK_ISSUER`, `DRF_RBAC_KEYCLOAK_CLIENT_ID`, and optionally
`DRF_RBAC_KEYCLOAK_AUDIENCE`. Hybrid adds KeycloakAuthentication after the local
classes. Business examples are ViewSet `/api/orders/` and APIView
`/api/order-details/<id>/`, using seeded `demo.order.*` permissions.

Development validation with complete SSO dependencies:

```bash
python -m pip install -e ".[dev,sso]"
python -m pytest -q
python example_project/manage.py check
python example_project/manage.py makemigrations --check --dry-run
python -m build
```

Verify the built wheel in a **new** virtual environment:

```bash
python -m venv .venv-wheel-check
# Activate its Scripts/Activate.ps1 on Windows or bin/activate on POSIX.
python -m pip install "./dist/drf_unified_rbac-0.2.0-py3-none-any.whl[sso]"
python -m pip check
python -I -c "import drf_unified_rbac; print(drf_unified_rbac.__version__, drf_unified_rbac.__file__)"
python -m pip install "pytest>=8.0" "pytest-django>=4.8"
python -m pytest -q
```

The imported package must reside in that environment's site-packages, not src.
Run example migrations in a fresh copy of the example without an existing
SQLite database. Tests use RSA-signed tokens and stub JWKS transport; no live
Keycloak server is needed. Actual release checks are recorded in
[PACKAGING_VALIDATION.md](PACKAGING_VALIDATION.md).

## Upgrade from 0.1.x

- Install 0.2.0; include `[sso]` for Keycloak authentication.
- Keep the existing host login and business ViewSet mappings. Select `hybrid`
  only when both local and SSO identities should be authorized.
- Keep the same URL include and `/api/rbac/me` fields. New admin routes live below
  `admin/`; bootstrap their permissions and bind the intended administrator.
- No new schema migration is required; normal `migrate` remains safe.
- **Intentional response semantics change:** SSO `get_roles()` / `me.roles` now
  exclude token roles missing or disabled in the RBAC database. Ensure expected
  Keycloak role codes have enabled RBAC Role rows. Permissions already required
  enabled database grants and retain that behavior.
- Invalid/unauthenticated user adapters and unknown explicit auth sources fail
  safely. Valid Django users and SSOUser retain the unified Principal contract.

Object-level permissions, data scopes, ABAC, multi-tenancy, user synchronization,
Keycloak administration, frontend code and host credential management remain
outside this release.
