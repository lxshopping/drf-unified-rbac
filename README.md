# drf-unified-rbac

`drf-unified-rbac` is a reusable Django app that provides role-based authorization for Django REST Framework. V0.1 implements local RBAC with Django's existing user model; it deliberately does not implement authentication, OIDC, JWT, or external identity mapping.

## Architecture

```text
Django User
    ↓ adapted by Principal.from_user()
Principal
    ↓ role lookup
LocalRoleProvider
    ↓ UserRole → enabled Role
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

`AUTH_MODE` defaults to `"local"`. V0.1 rejects `"oidc"` and every other unsupported value with `django.core.exceptions.ImproperlyConfigured`; there is no silent fallback.

The `UserRole.user` relation uses `settings.AUTH_USER_MODEL`, so the component works with Django's default user and normal custom user models.

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
GET  /api/orders/          demo.order.view
POST /api/orders/          demo.order.create
POST /api/orders/approve/  demo.order.approve
```

Authentication remains Django/DRF's responsibility. The example enables `SessionAuthentication` and `BasicAuthentication`; tests use `force_authenticate()`.

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

## V0.1 scope

V0.1 contains local authorization only. OIDC/Keycloak, JWT/JWKS, external identities, group mapping, object permissions, data scopes, ABAC, Redis, management APIs, frontend code, multi-tenancy, and audit systems are intentionally outside this release.
