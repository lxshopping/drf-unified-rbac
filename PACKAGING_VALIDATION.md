# 0.2.0 implementation and packaging validation

Validation date: 2026-09-17. This record describes the reusable RBAC package;
no consuming business project or frontend repository was modified.

## Result

- Version is 0.2.0 in both pyproject.toml and drf_unified_rbac.__version__.
- APIView and existing ViewSet declarations share default-deny RBACPermission.
- Local, SSO and Hybrid modes are implemented. Hybrid selects exactly one
  source-checked provider per principal; usernames/subjects never merge identities.
- Both providers return enabled database roles. In SSO, token roles absent from
  the RBAC database or disabled there are excluded from me.roles.
- Reusable, RBAC-protected administration APIs include pagination/search,
  soft-disable, and transactional complete relationship replacement.
- Bootstrap is idempotent and restores disabled/missing built-in grants. An
  already-complete bootstrap does not rewrite role/permission timestamps.
- No schema changes or new migrations. Keycloak token verification code is unchanged.
- Development full suite: **156 passed in 4.96s**.
- Installed-wheel full suite: **156 passed in 4.82s**, no collection errors.
- Django check, migration consistency, fresh database migration, and pip check pass.
- Both requested 0.2.0 distributions built successfully.

## Files and reasons

All source paths below are relative to src/drf_unified_rbac/ unless prefixed
with tests/ or example_project/.

| File | Reason |
| --- | --- |
| domain/principal.py | Validate authentication, supported source and SSO role shapes; retain unified from_user; remove obsolete commented SSO constructor. |
| permissions/drf.py | Accept APIView required_permission first, otherwise existing ViewSet action mapping; invalid declarations deny. |
| providers/hybrid.py (new) | Route each principal to its unique local/SSO provider. |
| providers/local.py | Retain independent source isolation and return no roles for malformed local primary keys. |
| providers/sso.py | Independently enforce SSO source and intersect token codes with enabled database roles. |
| providers/__init__.py | Export HybridRoleProvider. |
| factories/provider.py | Select HybridRoleProvider for hybrid; retain invalid-mode ImproperlyConfigured. |
| services/authorization.py | Keep service API/cache, validate permission codes and add clear_rbac_caches for both factories. |
| services/__init__.py | Export cache reset helper alongside the existing service exports. |
| views.py | Keep me contract and return 403 for invalid authenticated identity adaptation. |
| urls.py | Mount admin/ while preserving the original me path and URL name. |
| admin_api/__init__.py (new) | Package for reusable administration APIs. |
| admin_api/constants.py (new) | Single definition of the nine built-in management permissions. |
| admin_api/serializers.py (new) | Model representations, minimal host-user representation, and duplicate/unknown-code validation. |
| admin_api/views.py (new) | RBAC action mapping, bounded pagination/search, role soft-disable, atomic replacement with parent locks, minimal user-field queries. |
| admin_api/urls.py (new) | Register roles, permissions and local users with DRF routing. |
| management/__init__.py and management/commands/__init__.py (new) | Make management commands discoverable and included in the wheel. |
| management/commands/rbac_bootstrap_admin.py (new) | Transactional creation/recovery of rbac_admin and grants; optional existing-host-user binding. |
| __init__.py | Runtime version 0.2.0. |
| pyproject.toml | Distribution version 0.2.0; existing runtime ranges and SSO extra retained. |
| example_project/config/settings.py | Add hybrid authenticator selection and simplify environment settings. |
| example_project/config/urls.py | Register the APIView demonstration. |
| example_project/demo/views.py | Add a permission-protected APIView alongside the original ViewSet. |
| tests/conftest.py | joserfc signed-token and JWKS fixtures; shared cache reset. |
| tests/settings.py | Session middleware/app for real local-session Hybrid integration tests. |
| tests/test_factories.py | Cover invalid AUTH_MODE values, including wrong types. |
| tests/test_keycloak_authentication.py | Replace obsolete PyJWT mocks; exercise actual RS256 verification, required claims, JWKS caching, key refresh and failures. |
| tests/test_me.py | Adapt JWKS fixtures; expect only enabled known SSO roles. |
| tests/test_principal_and_provider.py | Supply database roles for the effective-role SSO provider contract. |
| tests/test_sso_integration.py | Use current JWKS interface while retaining ViewSet integration coverage. |
| tests/test_hybrid.py (new) | APIView declaration precedence/default deny, mode matrix, equal-name/equal-subject isolation, provider guards, live grants, cache reset and real session/signed-SSO me. |
| tests/test_admin_api.py (new) | Every endpoint's permission, CRUD, soft-disable, duplicate/unknown validation, replacement rollback, pagination/search, and SSO administration. |
| tests/test_bootstrap.py (new) | Idempotence including timestamps, disabled/missing grant recovery, existing users only, rollback and preservation of custom data. |
| tests/test_custom_user.py (new) | Launch an isolated Django consumer with a swapped user model. |
| tests/custom_user_check.py (new) | Exercise UUID IDs, non-username login, search, me, assignment, invalid IDs and bootstrap. |
| tests/custom_user_app/__init__.py and models.py (new) | Isolated custom-user test app with UUID pk and USERNAME_FIELD=login. |
| README.md | Installation, three modes, view declarations, administration contract, bootstrap, host-auth boundary/Bearer routing, frontend contract and upgrade notes. |
| PACKAGING_VALIDATION.md | This implementation and release validation record. |

No text changes were needed in models, migrations, conf.py, apps.py, admin.py,
PermissionRepository or authentication/keycloak.py. Original ViewSet, model,
repository and authorization tests remain part of the full passing suite.
At task start, 57 tracked files already had executable-bit differences; these
were preserved. Files listed by git status solely for those mode differences
are not new content changes from this implementation.

## Public behavior and compatibility

| Mode | Local principal | SSO principal | Unknown source |
| --- | --- | --- | --- |
| local | UserRole -> enabled Role | No grants | No grants |
| sso | No grants | Token client codes -> enabled Role | No grants |
| hybrid | Local provider only | SSO provider only | No grants |

AuthorizationService retains get_roles(principal), get_permissions(principal)
and has_permission(principal, permission_code). Cached construction remains;
HybridRoleProvider routes at each call. No user roles/permissions are cached.
clear_rbac_caches() clears provider and service caches after settings changes.

RBACPermission first accepts a non-blank string required_permission. Otherwise
it resolves required_permissions[view.action]. Invalid/missing declarations,
identity or grants deny. No staff/superuser bypass was introduced.

GET /api/rbac/me retains its no-trailing-slash path, URL name and fields:
username, auth_source, sorted unique roles, sorted unique permissions. It uses
IsAuthenticated without a business grant requirement. Valid users without grants
receive 200 with empty arrays. Invalid principal adaptation receives 403.

**Intentional compatibility change:** SSO get_roles()/me.roles now report only
enabled RBAC database roles. Raw token roles that are unknown or disabled no
longer appear. RolePermission/Permission enabled filtering remains in effect.
Local/sso mode configuration, ViewSet declarations, service APIs and valid user
adaptation remain compatible. More restrictive invalid-user handling is deliberate.

No database migration was added; the field is enabled, not is_active. User data
comes from get_user_model(), with only pk/get_username()/optional is_active
serialized. Local account creation/password management and Keycloak Admin API
operations remain outside the package.

## Administration contract

Paths are relative to /api/rbac/admin/:

| Path | Methods | Permission |
| --- | --- | --- |
| roles/ | GET, POST | rbac.role.view/create |
| roles/<id>/ | GET, PATCH, DELETE | rbac.role.view/update/delete |
| permissions/ | GET, POST | rbac.permission.view/create |
| permissions/<id>/ | GET, PATCH | rbac.permission.view/update |
| roles/<id>/permissions/ | GET, PUT | rbac.role.view/update |
| users/ | GET | rbac.user_role.view |
| users/<id>/roles/ | GET, PUT | rbac.user_role.view/update |

Role DELETE sets enabled=False and preserves relations. Lists are paginated
(default 50, client maximum 200) and searchable (?search=). Roles/permissions
search code/name; users search USERNAME_FIELD. The list response is the DRF
count/next/previous/results shape.

Relationship PUT takes permission_codes or role_codes arrays, validates all codes,
rejects duplicates, and replaces the complete set in transaction.atomic(). Parent
row locking serializes replacements on databases supporting SELECT FOR UPDATE;
SQLite's locking differs. Empty arrays clear assignments. Admin relationship GET
shows stored assignments, while me shows effective enabled roles/permissions.

Bootstrap usage:

```bash
python manage.py rbac_bootstrap_admin
python manage.py rbac_bootstrap_admin --username admin
```

Every run ensures nine built-in permissions and rbac_admin are present/enabled
and all built-in relations exist. The optional username is resolved using the
host's USERNAME_FIELD; it binds an existing local user only. For SSO, assign
Keycloak client role rbac_admin in the configured client; no local user is needed.

## Test environments and commands

Host: Windows, Python 3.12.14. Runtime versions resolved for validation:
Django 5.2.17, DRF 3.18.1, joserfc 1.7.5, cryptography 50.0.1.
Test tooling: pytest 9.1.1 and pytest-django 4.14.0.
Build isolation: setuptools 84.0.0 and wheel 0.48.0.

A new .venv-rbac-020-dev environment installed .[dev,sso]. Tests use the installed
editable app and include full SSO dependencies. Final run:

```text
156 passed in 4.96s
```

The initial repository environment failed collection because joserfc was absent;
old SSO tests also mocked the retired get_jwk_client/PyJWT interface. Those issues
were resolved with the complete dependency environment and updated signed-token
fixtures; the initial 28 passing non-SSO tests are not the completion criterion.

```text
python example_project/manage.py check
System check identified no issues (0 silenced).

python example_project/manage.py makemigrations --check --dry-run
No changes detected
```

First network-backed build produced sdist but failed fetching setuptools for
the second isolated environment. After downloading dependencies into the ignored
build/wheelhouse directory, the standard build was rerun with isolated dependency
installation sourced locally:

```powershell
$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
$env:PIP_NO_INDEX='1'
$env:PIP_FIND_LINKS='E:\code\drf-unified-rbac\build\wheelhouse'
& .\.venv-rbac-020-dev\Scripts\python.exe -m build
```

```text
Successfully built drf_unified_rbac-0.2.0.tar.gz and drf_unified_rbac-0.2.0-py3-none-any.whl
```

This retained build isolation and built the wheel from the sdist. No package-index
configuration or dependency constraints in the repository were changed.

## Clean wheel installation

Created a separate .venv-rbac-020-wheel with system site packages disabled.
First installed only the base wheel and dependencies. A standalone consumer
confirmed local functionality without joserfc installed. Then installed the same
wheel's [sso] extra and test tools from the downloaded dependency directory.
No editable app install or src PYTHONPATH was used in this environment.

```text
Import: E:\code\drf-unified-rbac\.venv-rbac-020-wheel\Lib\site-packages\drf_unified_rbac\__init__.py
Runtime version = installed metadata version = 0.2.0
No broken requirements found.
```

Consumer checks ran from build/package-validation-020 against a fresh copy of
example_project, using a fresh in-memory database for each mode. The existing
example database was not migrated or seeded by these checks.

| Check | Result |
| --- | --- |
| Base installation without SSO dependency | Passed local consumer checks. |
| Isolated `python -I` import | site-packages and metadata/runtime version 0.2.0. |
| Fresh migrate and Django checks | Passed in local, sso and hybrid. |
| URL include/reverse | Original /api/rbac/me resolves; new admin URLs resolve. |
| APIView and ViewSet | Authorized GET succeeds; ungranted create denied. |
| Local session and SSO signed-token me | Effective, sorted roles/permissions; no cross-source merge. |
| RBAC administration | Paginated roles and authorized creation succeed. |
| Bootstrap | Repeated command succeeds and grants remain complete. |
| Invalid SSO token | Authentication failure; no fallback. |
| SSO identity | No local user automatically created. |
| Installed-wheel full test suite | 156 passed in 4.82s, zero collection errors. |
| pip check | No broken requirements found. |

The tests and example copied for installed-wheel verification contain no src
package. The copied test suite also runs the custom-user consumer subprocess
using the wheel-installed app.

Archive checks compared every Python app module byte-for-byte with the workspace.
The wheel contains 38 Python modules plus distribution metadata, including the
new admin_api and management packages and existing migrations. It contains no
tests, example, database or temporary files. The sdist includes matching app,
example, tests, README and build/test configuration. git diff --check passes.

## Artifacts

- `drf_unified_rbac-0.2.0-py3-none-any.whl`: 29013 bytes; SHA-256 `f2440938c4d09ad97f68e16befc1238d99e668174bcc87b332641ef599fa08d4`.
- `drf_unified_rbac-0.2.0.tar.gz`: 43431 bytes; SHA-256 `dfc5a080b15795b99f06f8bf8599c72609666248359e5d4c68e5373fbb2698bf`.

The validation record is repository documentation, outside the wheel and sdist;
artifact hashes above refer to the exact archives installed and checked.

## Consumer upgrade steps

1. Upgrade the wheel to 0.2.0, using [sso] where Keycloak authentication is needed.
2. Keep the host's local login and password/session/JWT implementation.
3. For dual identity support, set AUTH_MODE=hybrid and configure the host's
   authentication classes alongside KeycloakAuthentication. If both consume
   Bearer, the host must define explicit routing; this package adds no fallback.
4. Keep the existing URL include and ViewSet mappings; APIViews can now declare
   required_permission. me response fields remain unchanged.
5. Run normal migrate (no new schema changes), bootstrap management permissions,
   and bind the intended existing local administrator or Keycloak client role.
6. Ensure expected SSO role codes have enabled database Role entries.
7. Both login flows call GET /api/rbac/me; frontend authorization consumes
   me.permissions. No frontend repository change is part of this task.

## Verification limits

Tests used SQLite and locally signed RSA tokens with stub JWKS transport. No live
Keycloak deployment or PostgreSQL/MySQL concurrency test was run. The declared
Python/Django/DRF compatibility ranges were retained; this run validates the
versions listed above rather than a full supported-version matrix.
