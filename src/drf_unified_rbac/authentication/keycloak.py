import json
import time
from collections.abc import Mapping
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ImproperlyConfigured
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from drf_unified_rbac.conf import get_rbac_setting, get_required_rbac_string
from drf_unified_rbac.domain.principal import extract_client_role_codes


# Keycloak JWKS 一般不会频繁变化。
# 缓存 5 分钟，避免每个 API 请求都访问一次 Keycloak。
_JWKS_CACHE_TTL = 300

_jwks_cache: dict[str, tuple[float, KeySet]] = {}
_jwks_cache_lock = Lock()


def get_jwk_set(jwks_url: str, *, force_refresh: bool = False) -> KeySet:
    """Fetch and cache Keycloak's JWKS."""

    now = time.monotonic()

    if not force_refresh:
        cached = _jwks_cache.get(jwks_url)

        if cached is not None:
            cached_at, key_set = cached

            if now - cached_at < _JWKS_CACHE_TTL:
                return key_set

    request = Request(
        jwks_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "drf-unified-rbac/0.1",
        },
    )

    try:
        with urlopen(request, timeout=5) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise AuthenticationFailed(
            "Unable to load Keycloak signing keys."
        ) from exc

    if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
        raise AuthenticationFailed(
            "Invalid Keycloak JWKS response."
        )

    try:
        key_set = KeySet.import_key_set(data)
    except (TypeError, ValueError) as exc:
        raise AuthenticationFailed(
            "Invalid Keycloak signing keys."
        ) from exc

    with _jwks_cache_lock:
        _jwks_cache[jwks_url] = (now, key_set)

    return key_set


def decode_keycloak_token(
    token: str,
    *,
    jwks_url: str,
    issuer: str,
    audience: str,
) -> dict[str, Any]:
    """Verify Keycloak access token signature and required claims."""

    key_set = get_jwk_set(jwks_url)

    try:
        token_obj = jwt.decode(
            token,
            key_set,
            algorithms=["RS256"],
        )

        claims_registry = JWTClaimsRegistry(
            exp={
                "essential": True,
            },
            iss={
                "essential": True,
                "value": issuer,
            },
            aud={
                "essential": True,
                "values": [audience],
            },
            sub={
                "essential": True,
            },
        )

        claims_registry.validate(token_obj.claims)

    except JoseError:
        # Keycloak 发生 key rotation 时，
        # 当前缓存里可能没有新 kid。
        # 刷新 JWKS 后再尝试一次。
        try:
            key_set = get_jwk_set(
                jwks_url,
                force_refresh=True,
            )

            token_obj = jwt.decode(
                token,
                key_set,
                algorithms=["RS256"],
            )

            claims_registry = JWTClaimsRegistry(
                exp={
                    "essential": True,
                },
                iss={
                    "essential": True,
                    "value": issuer,
                },
                aud={
                    "essential": True,
                    "values": [audience],
                },
                sub={
                    "essential": True,
                },
            )

            claims_registry.validate(token_obj.claims)

        except (JoseError, ValueError, TypeError) as exc:
            raise AuthenticationFailed(
                "Invalid Keycloak access token."
            ) from exc

    claims = dict(token_obj.claims)

    return claims


class SSOUser:
    """A lightweight authenticated user backed only by verified token claims."""

    auth_source = "sso"

    def __init__(self, claims: Mapping[str, Any], client_id: str) -> None:
        subject = claims.get("sub")

        if not isinstance(subject, str) or not subject:
            raise ValueError(
                "The access token does not contain a valid subject"
            )

        preferred_username = claims.get("preferred_username")

        self.subject = subject

        self.username = (
            preferred_username
            if isinstance(preferred_username, str)
            and preferred_username
            else subject
        )

        self.claims = dict(claims)

        self.role_codes = extract_client_role_codes(
            claims,
            client_id,
        )

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

    def authenticate(
        self,
        request: Any,
    ) -> tuple[SSOUser, dict[str, Any]] | None:

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
            raise AuthenticationFailed(
                "Invalid bearer token header."
            ) from exc

        issuer = get_required_rbac_string(
            "KEYCLOAK_ISSUER"
        )

        client_id = get_required_rbac_string(
            "KEYCLOAK_CLIENT_ID"
        )

        configured_audience = get_rbac_setting(
            "KEYCLOAK_AUDIENCE"
        )

        if configured_audience is None:
            audience = client_id

        elif (
            isinstance(configured_audience, str)
            and configured_audience.strip()
        ):
            audience = configured_audience.strip()

        else:
            raise ImproperlyConfigured(
                "DRF_RBAC.KEYCLOAK_AUDIENCE "
                "must be a non-empty string or None"
            )

        jwks_url = (
            f"{issuer.rstrip('/')}"
            "/protocol/openid-connect/certs"
        )

        try:
            claims = decode_keycloak_token(
                token,
                jwks_url=jwks_url,
                issuer=issuer,
                audience=audience,
            )

            user = SSOUser(
                claims,
                client_id,
            )

        except ValueError as exc:
            raise AuthenticationFailed(
                "Invalid Keycloak access token."
            ) from exc

        return user, claims

    def authenticate_header(self, request: Any) -> str:
        return "Bearer"