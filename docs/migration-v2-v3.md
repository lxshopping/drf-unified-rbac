# V2 (0.2.0) to V3 (0.3.0)

Install 0.3.0 with the sso extra for Keycloak/Hybrid deployments. Existing
required_permissions mappings, APIView required_permission, permission codes,
Role/Permission/UserRole data, Admin APIs and ADMIN_PERMISSIONS are unchanged.
No database migration is added: UserRole and the initial swappable dependency
already reference settings.AUTH_USER_MODEL. Run normal migrate for a new project.

Keep Keycloak issuer/client/audience configuration. RS256, iss/aud/exp/sub
validation, JWKS handling and client-role mapping are unchanged. me remains
GET /api/rbac/me with username, auth_source, sorted roles and permissions.
Source mismatches still produce empty grants, preserving V2 behavior.

Existing host login need not be replaced. Set DRF_RBAC.LOCAL_LOGIN_ENABLED=False
to disable package login/logout/CSRF endpoints. Local authorization and host
DEFAULT_AUTHENTICATION_CLASSES continue to work. A broken Local adapter cannot
affect host-authenticated authorization because only package login loads it.

For new projects the default adapter delegates to Django authenticate and the
endpoint calls Django login. Enable Django session/auth/CSRF middleware and DRF
SessionAuthentication. Use the CSRF endpoint before login and again after login
rotation. No new runtime dependencies, password storage or JWT issuer exist.
A custom user USERNAME_FIELD still accepts the default endpoint's username key
through Django ModelBackend. Custom backends can translate it in an adapter.

Intentional security change: me in sso/hybrid validates Keycloak Bearer before
host authentication, even if a valid Local session cookie is also present. A
malformed, expired or invalid token cannot fall back to Local. No Bearer allows
normal host authentication. me still retains all configured host authenticators.
Business and Admin APIs remain host configured: put KeycloakAuthentication before
SessionAuthentication and any authenticator which would otherwise bypass Bearer.
The example now follows that order. Do not globally replace host DRF settings.

If a host also uses Bearer for its own tokens, explicitly route credentials in a
host-owned MeView subclass/get_authenticators or separate routes. Package me
reserves Bearer for Keycloak in sso/hybrid; it cannot infer two token owners.
Do not route by username or recover from failed token validation using a session.

The adapter factory is lazy and uncached, and validates a concrete
BaseLocalAuthAdapter subclass. Provider/service cache APIs remain unchanged;
clear_rbac_caches remains available after deliberate AUTH_MODE reloads.
No source-level authorization API was removed. Principal.from_sso is an additive
explicit SSO entry point; Principal.from_user still accepts both identity types.
