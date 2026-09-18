# drf-unified-rbac

Reusable Django/DRF authorization for local Django users, Keycloak SSO users,
and both together. Version **0.3.0** adds a configurable Local Login Adapter and
Django Session login/logout, preserving the V2 authorization and Admin APIs.

## Authentication and authorization

New projects can use the package Local login endpoint with Django Auth. Existing
hosts can keep their login and DRF authentication unchanged. RBAC does not own a
User model, store passwords separately, or issue JWTs. All local users belong to
the host AUTH_USER_MODEL; credential verification uses AUTHENTICATION_BACKENDS.
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
dist/drf_unified_rbac-0.3.0-py3-none-any.whl
dist/drf_unified_rbac-0.3.0.tar.gz
```

Local-only consumers install the wheel:

```bash
python -m pip install ./dist/drf_unified_rbac-0.3.0-py3-none-any.whl
```

SSO and Hybrid consumers install the SSO extra:

```bash
python -m pip install "./dist/drf_unified_rbac-0.3.0-py3-none-any.whl[sso]"
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
Permission, RolePermission and UserRole. Version 0.3.0 needs no new schema
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
        "drf_unified_rbac.authentication.KeycloakAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}
```

DRF uses the first authenticator that succeeds. Put KeycloakAuthentication first:
an invalid Bearer must fail even when a valid local session exists. With no Bearer,
Keycloak returns None and the host authenticator can handle the local identity.
Session-authenticated unsafe requests retain DRF CSRF requirements. The package
me endpoint enforces Keycloak-first in sso/hybrid while retaining host classes.
Business and Admin APIs still use the host authentication configuration; configure
the same safe ordering there. No global DRF settings are overwritten.

For host JWT authentication, configure the host class together with
KeycloakAuthentication, **only with an explicit host authentication-routing contract**. If both consume `Authorization: Bearer`, listing both classes alone
does not define safe routing. The host must distinguish which authenticator owns
the credential, returning `None` only for credentials outside its scheme or
route, and must fully verify the selected token. Do not catch a failed token
validation and fall back to another identity. This package does not automatically
route two Bearer authenticators or reimplement host authentication. In sso/hybrid,
the package me endpoint reserves Bearer for Keycloak. A host using its own Bearer
tokens must expose a host-owned MeView subclass with explicit get_authenticators
routing, or use separate routes; never fall back after failed verification.

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
Local login button -> package or host local login API -> keep host credentials -> GET /api/rbac/me
SSO login button   -> Keycloak code flow -> callback/access token -> GET /api/rbac/me
```

After either flow, menus, routes, pages and buttons consume `me.permissions`.
The post-login authorization logic is identical; do not derive permissions from
`auth_source` or usernames. Server-side RBAC remains authoritative. The frontend,
redirect/callback handling and existing host login implementation remain host-owned.

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
`DRF_RBAC_KEYCLOAK_AUDIENCE`. Hybrid puts KeycloakAuthentication before the local
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
python -m pip install "./dist/drf_unified_rbac-0.3.0-py3-none-any.whl[sso]"
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

- Install 0.3.0; include `[sso]` for Keycloak authentication.
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


## V3 Local Login Adapter

Four supported integration paths share the existing authorization core:

| Scenario | Authentication path | Authorization path |
| --- | --- | --- |
| A: New Django project | package login -> LocalAuthAdapter -> Django authenticate/login -> Session -> request.user | Principal.from_user -> LocalRoleProvider -> RBAC |
| B: Existing host Local | host login/authenticator -> request.user; no package adapter call | Principal.from_user -> LocalRoleProvider -> RBAC |
| C: Keycloak | verified Bearer -> KeycloakAuthentication -> SSOUser | Principal.from_sso (or from_user) -> SSORoleProvider -> RBAC |
| D: Hybrid | Keycloak Bearer first, otherwise host/Session authentication | auth_source selects one provider -> unified me and permissions |

RBAC here means AuthorizationService -> Role/RolePermission/Permission. Local
assignments use UserRole. Django user.has_perm and Django Permission do not
replace RBAC grants. Authentication is never repeated inside RBACPermission,
AuthorizationService, or me.

Configuration uses the existing dictionary only:

```python
DRF_RBAC = {
    "AUTH_MODE": "local",  # local / sso / hybrid
    "LOCAL_LOGIN_ENABLED": True,
    "LOCAL_AUTH_ADAPTER": "drf_unified_rbac.authentication.adapters.DjangoLocalAuthAdapter",
}
```

LOCAL_LOGIN_ENABLED must be a boolean, and LOCAL_AUTH_ADAPTER a dotted class
path. Invalid settings or adapter construction raise ImproperlyConfigured; they
never grant access. Adapters load lazily per login, with no shared request state.
Existing Keycloak issuer/client/audience settings retain their meaning.

New projects enable django.contrib.auth/contenttypes/sessions, SessionMiddleware,
CsrfViewMiddleware, AuthenticationMiddleware, and DRF SessionAuthentication.
Run migrate and provision users using normal Django tools. No RBAC User model,
password table, JWT signing, or additional dependency is introduced.

| Endpoint (no trailing slash) | Result |
| --- | --- |
| GET /api/rbac/auth/local/csrf | 200 {"csrfToken": "..."}, no-store; initialize CSRF cookie/session |
| POST /api/rbac/auth/local/login | username/password -> 200 {"authenticated": true} |
| POST /api/rbac/auth/local/logout | flush Django session -> 204 (also safe when already logged out) |

Login accepts JSON or form username/password strings. Wrong password, unknown or
inactive user, rejected/invalid adapter identity all return the same 401 detail:
Authentication failed. Invalid JSON is a DRF 400. Missing/invalid CSRF is 403.
Login does not compute roles or permissions; call GET /api/rbac/me afterward.
Login rotates the CSRF secret: get a fresh token before logout. Both POSTs enforce
CSRF even for anonymous callers. Clients preserve cookies and send X-CSRFToken.
The CSRF endpoint also supports CSRF_USE_SESSIONS and CSRF_COOKIE_HTTPONLY.
Logout ends only the Django session, not a Keycloak session or access token.

All three local endpoints return 404 when LOCAL_LOGIN_ENABLED=False or AUTH_MODE
is sso. Host-authenticated Local users and authorization continue to work when
the endpoints are disabled. me and protected APIs never load the Local adapter.

To customize credential verification, subclass BaseLocalAuthAdapter and configure
its dotted path. Implement authenticate(request, **credentials), returning a
persisted, active Django-compatible local user or None / AuthenticationFailed.
The package endpoint passes username/password; translate them in the adapter for
custom backend needs. Direct callers can supply additional credentials. Delegate
to django.contrib.auth.authenticate whenever possible: it sets user.backend.
With multiple AUTHENTICATION_BACKENDS a custom adapter must set the correct
backend path, whose get_user can restore this user from the session. Adapters
must not compute RBAC grants. Exception details are not returned to clients.

### Example Local session walkthrough

After migrate, seed_demo_rbac and createsuperuser, assign a demo role (staff or
superuser alone does not grant RBAC business permissions):

```python
# python example_project/manage.py shell
from django.contrib.auth import get_user_model
from drf_unified_rbac.models import Role, UserRole
user = get_user_model().objects.get_by_natural_key("admin")
UserRole.objects.get_or_create(user=user, role=Role.objects.get(code="demo_admin"))
```

Start runserver, then execute this client script using Python's standard library:

```python
import getpass
import http.cookiejar
import json
from urllib.request import build_opener, HTTPCookieProcessor, Request

client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
base = "http://127.0.0.1:8000"
def call(path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-CSRFToken"] = token
    body = None if data is None else json.dumps(data).encode()
    with client.open(Request(base + path, body, headers)) as response:
        payload = response.read()
        return json.loads(payload) if payload else response.status

token = call("/api/rbac/auth/local/csrf")["csrfToken"]
print(call("/api/rbac/auth/local/login", {
    "username": "admin", "password": getpass.getpass(),
}, token))
print(call("/api/rbac/me"))
print(call("/api/orders/"))
token = call("/api/rbac/auth/local/csrf")["csrfToken"]
print(call("/api/rbac/auth/local/logout", {}, token))
# A subsequent me request is rejected as unauthenticated.
```

See [V2 to V3 migration](docs/migration-v2-v3.md) for compatibility and Hybrid
credential precedence changes.
