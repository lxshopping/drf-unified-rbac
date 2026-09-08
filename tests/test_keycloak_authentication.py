from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from jwt.exceptions import PyJWKClientError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

import drf_unified_rbac.authentication.keycloak as keycloak_module
from drf_unified_rbac.authentication import KeycloakAuthentication, SSOUser


class StaticJWKClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.public_key)


def request_with_authorization(value=None):
    headers = {"HTTP_AUTHORIZATION": value} if value is not None else {}
    return APIRequestFactory().get("/api/orders/", **headers)


def authenticate(token):
    request = request_with_authorization(f"Bearer {token}")
    return KeycloakAuthentication().authenticate(request)


def test_no_authorization_header_returns_none():
    assert KeycloakAuthentication().authenticate(request_with_authorization()) is None


def test_non_bearer_authorization_returns_none():
    request = request_with_authorization("Basic credentials")

    assert KeycloakAuthentication().authenticate(request) is None


@pytest.mark.parametrize("header", ["Bearer", "Bearer one two"])
def test_malformed_bearer_header_raises_authentication_failed(header):
    with pytest.raises(AuthenticationFailed):
        KeycloakAuthentication().authenticate(request_with_authorization(header))


def test_valid_keycloak_token_returns_sso_user_and_claims(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )
    token = make_keycloak_token()

    with override_settings(DRF_RBAC=keycloak_config):
        user, claims = authenticate(token)

    assert isinstance(user, SSOUser)
    assert user.subject == "keycloak-user-123"
    assert user.username == "alice.sso"
    assert user.is_authenticated is True
    assert user.is_anonymous is False
    assert user.role_codes == ("admin", "operator")
    assert claims == user.claims


def test_username_falls_back_to_subject(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )
    token = make_keycloak_token(preferred_username=None)

    with override_settings(DRF_RBAC=keycloak_config):
        user, _ = authenticate(token)

    assert user.username == "keycloak-user-123"


def test_token_with_invalid_signature_is_rejected(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
):
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )

    with override_settings(DRF_RBAC=keycloak_config):
        with pytest.raises(AuthenticationFailed):
            authenticate(make_keycloak_token(signing_key=wrong_key))


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"iss": "https://wrong-issuer.example.test/realms/demo"},
        {"aud": "wrong-audience"},
    ],
    ids=["expired", "invalid-issuer", "invalid-audience"],
)
def test_invalid_registered_claim_is_rejected(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
    overrides,
):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )

    with override_settings(DRF_RBAC=keycloak_config):
        with pytest.raises(AuthenticationFailed):
            authenticate(make_keycloak_token(**overrides))


def test_malformed_token_is_rejected(monkeypatch, keycloak_config):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(None),
    )

    with override_settings(DRF_RBAC=keycloak_config):
        with pytest.raises(AuthenticationFailed):
            authenticate("not-a-jwt")


def test_signing_key_lookup_failure_is_rejected(monkeypatch, keycloak_config):
    class FailingJWKClient:
        def get_signing_key_from_jwt(self, token):
            raise PyJWKClientError("JWKS unavailable")

    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: FailingJWKClient(),
    )

    with override_settings(DRF_RBAC=keycloak_config):
        with pytest.raises(AuthenticationFailed):
            authenticate("header.payload.signature")


def test_audience_defaults_to_client_id(
    monkeypatch,
    keycloak_config,
    keycloak_public_key,
    make_keycloak_token,
):
    monkeypatch.setattr(
        keycloak_module,
        "get_jwk_client",
        lambda url: StaticJWKClient(keycloak_public_key),
    )
    config = {**keycloak_config, "KEYCLOAK_AUDIENCE": None}
    token = make_keycloak_token(aud=keycloak_config["KEYCLOAK_CLIENT_ID"])

    with override_settings(DRF_RBAC=config):
        user, _ = authenticate(token)

    assert user.is_authenticated is True
