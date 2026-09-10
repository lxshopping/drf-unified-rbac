from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def extract_client_role_codes(
    claims: Mapping[str, Any], client_id: str
) -> tuple[str, ...]:
    """Normalize roles from the configured client in verified claims only."""
    resource_access = claims.get("resource_access")
    if not isinstance(resource_access, Mapping):
        return ()
    client_access = resource_access.get(client_id)
    if not isinstance(client_access, Mapping):
        return ()
    roles = client_access.get("roles")
    if not isinstance(roles, list):
        return ()
    return tuple(sorted({role for role in roles if isinstance(role, str) and role.strip()}))


@dataclass(frozen=True)
class Principal:
    """Authentication-neutral identity used by the authorization layer."""

    subject: str
    username: str
    auth_source: str
    claims: Mapping[str, Any] | None = field(default=None, compare=False, repr=False)
    role_codes: tuple[str, ...] = ()

    @classmethod
    def from_user(cls, user: Any) -> "Principal":
        """Adapt an authenticated local or SSO user without requiring an SSO pk."""
        if getattr(user, "auth_source", None) == "sso":
            subject = getattr(user, "subject", None)
            claims = getattr(user, "claims", None)
            role_codes = getattr(user, "role_codes", ())

            if not isinstance(subject, str) or not subject:
                raise ValueError("SSO user does not contain a valid subject")
            if not isinstance(claims, Mapping):
                raise ValueError("SSO user does not contain valid claims")

            return cls(
                subject=user.subject,
                username=user.get_username(),
                auth_source="sso",
                claims=user.claims,
                role_codes=tuple(user.role_codes),
            )
        return cls.from_local_user(user)

    @classmethod
    def from_local_user(cls, user: Any) -> "Principal":
        """Adapt an authenticated Django user to a local principal."""
        if getattr(user, "pk", None) is None:
            raise ValueError("Local user does not contain a valid pk")
        
        return cls(
            subject=str(user.pk),
            username=str(user.get_username()),
            auth_source="local",
            claims=None,
            role_codes=(),
        )

    # @classmethod
    # def from_sso_claims(
    #     cls, claims: Mapping[str, Any], client_id: str | None = None
    # ) -> "Principal":
    #     if client_id is None:
    #         from drf_unified_rbac.conf import get_required_rbac_string

    #         client_id = get_required_rbac_string("KEYCLOAK_CLIENT_ID")
    #     subject = claims.get("sub")
    #     if not isinstance(subject, str) or not subject:
    #         raise ValueError("The access token does not contain a valid subject")
    #     username = claims.get("preferred_username")
    #     return cls(
    #         subject=subject,
    #         username=username if isinstance(username, str) and username else subject,
    #         auth_source="sso",
    #         claims=claims,
    #         role_codes=extract_client_role_codes(claims, client_id),
    #     )
