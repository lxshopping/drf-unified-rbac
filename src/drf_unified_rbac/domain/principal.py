from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Principal:
    """Authentication-neutral identity used by the authorization layer."""

    subject: str
    username: str
    auth_source: str

    @classmethod
    def from_user(cls, user: Any) -> "Principal":
        """Adapt an authenticated Django user to a local principal."""
        return cls(
            subject=str(user.pk),
            username=str(user.get_username()),
            auth_source="local",
        )

