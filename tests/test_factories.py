import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from drf_unified_rbac.factories import get_role_provider
from drf_unified_rbac.providers import LocalRoleProvider, SSORoleProvider
from drf_unified_rbac.services import get_authorization_service


@override_settings(DRF_RBAC={"AUTH_MODE": "local"})
def test_local_auth_mode_returns_local_provider():
    assert isinstance(get_role_provider(), LocalRoleProvider)


@override_settings(DRF_RBAC={"AUTH_MODE": "sso"})
def test_sso_auth_mode_returns_sso_provider():
    assert isinstance(get_role_provider(), SSORoleProvider)


@override_settings(DRF_RBAC={"AUTH_MODE": "oidc"})
def test_unknown_auth_mode_raises_configuration_error():
    with pytest.raises(ImproperlyConfigured, match="Unsupported AUTH_MODE"):
        get_role_provider()


def test_provider_is_reused_within_process():
    assert get_role_provider() is get_role_provider()


def test_authorization_service_is_reused_within_process():
    assert get_authorization_service() is get_authorization_service()
