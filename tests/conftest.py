import pytest

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

