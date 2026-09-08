from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError, PyJWTError
from django.core.exceptions import ImproperlyConfigured
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from drf_unified_rbac.conf import get_rbac_setting, get_required_rbac_string
from drf_unified_rbac.domain.principal import extract_client_role_codes


@lru_cache(maxsize=8)
def get_jwk_client(jwks_url: str) -> PyJWKClient:
    """Reuse PyJWT's caching JWKS client for each configured Keycloak realm."""
    return PyJWKClient(jwks_url)


class SSOUser:
    """A lightweight authenticated user backed only by verified token claims."""

    auth_source = "sso"

    def __init__(self, claims: Mapping[str, Any], client_id: str) -> None:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("The access token does not contain a valid subject")

        preferred_username = claims.get("preferred_username")
        self.subject = subject
        self.username = (
            preferred_username
            if isinstance(preferred_username, str) and preferred_username
            else subject
        )
        self.claims = dict(claims)
        self.role_codes = extract_client_role_codes(claims, client_id)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_username(self) -> str:
        return self.username

    def __str__(self) -> str:
        return self.username


class KeycloakAuthentication(BaseAuthentication):
    """Authenticate Keycloak access tokens using the realm's JWKS endpoint."""

    keyword = b"bearer"

    def authenticate(self, request: Any) -> tuple[SSOUser, dict[str, Any]] | None:
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword:
            return None
        if len(auth) == 1:
            raise AuthenticationFailed(
                "Invalid bearer token header: no credentials provided."
            )
        if len(auth) != 2:
            raise AuthenticationFailed(
                "Invalid bearer token header: token must not contain spaces."
            )

        try:
            token = auth[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Invalid bearer token header.") from exc

        issuer = get_required_rbac_string("KEYCLOAK_ISSUER")
        client_id = get_required_rbac_string("KEYCLOAK_CLIENT_ID")
        configured_audience = get_rbac_setting("KEYCLOAK_AUDIENCE")
        if configured_audience is None:
            audience = client_id
        elif isinstance(configured_audience, str) and configured_audience.strip():
            audience = configured_audience.strip()
        else:
            raise ImproperlyConfigured(
                "DRF_RBAC.KEYCLOAK_AUDIENCE must be a non-empty string or None"
            )

        jwks_url = f"{issuer.rstrip('/')}/protocol/openid-connect/certs"
        try:
            signing_key = get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer,
                audience=audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            user = SSOUser(claims, client_id)
        except (PyJWTError, PyJWKClientError, ValueError) as exc:
            raise AuthenticationFailed("Invalid Keycloak access token.") from exc

        return user, claims

    def authenticate_header(self, request: Any) -> str:
        return "Bearer"
