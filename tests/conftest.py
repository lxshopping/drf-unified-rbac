from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from drf_unified_rbac.factories import get_role_provider
from drf_unified_rbac.services import get_authorization_service


@pytest.fixture(autouse=True)
def clear_singleton_like_caches():
    get_authorization_service.cache_clear()
    get_role_provider.cache_clear()
    yield
    get_authorization_service.cache_clear()
    get_role_provider.cache_clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="alice",
        password="unused",
    )


@pytest.fixture(scope="session")
def keycloak_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def keycloak_public_key(keycloak_private_key):
    return keycloak_private_key.public_key()


@pytest.fixture
def keycloak_config():
    return {
        "AUTH_MODE": "sso",
        "KEYCLOAK_ISSUER": "https://sso.example.test/realms/demo",
        "KEYCLOAK_CLIENT_ID": "my-app",
        "KEYCLOAK_AUDIENCE": "my-api",
    }


@pytest.fixture
def make_keycloak_token(keycloak_private_key, keycloak_config):
    def make_token(*, signing_key=None, **overrides):
        claims = {
            "sub": "keycloak-user-123",
            "preferred_username": "alice.sso",
            "iss": keycloak_config["KEYCLOAK_ISSUER"],
            "aud": keycloak_config["KEYCLOAK_AUDIENCE"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "resource_access": {
                keycloak_config["KEYCLOAK_CLIENT_ID"]: {
                    "roles": ["admin", "operator"],
                }
            },
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            signing_key or keycloak_private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    return make_token
