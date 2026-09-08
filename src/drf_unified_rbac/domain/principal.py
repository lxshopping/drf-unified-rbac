from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Principal:
    """Authentication-neutral identity used by the authorization layer."""

    subject: str
    username: str
    auth_source: str
    claims: Mapping[str, Any] | None = None

    @classmethod
    def from_local_user(cls, user: Any) -> "Principal":
        """Adapt an authenticated Django user to a local principal."""
        return cls(
            subject=str(user.pk),
            username=str(user.get_username()),
            auth_source="local",
            claims=None,
        )

    @classmethod
    def from_sso_claims(cls, claims: dict[str, Any]) -> "Principal":
        return cls(
            subject=str(claims["sub"]),
            username=str(claims["preferred_username"]),
            auth_source="sso",
            claims=claims,
        )