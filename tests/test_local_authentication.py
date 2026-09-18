import pytest
from django.contrib import auth
from django.core.exceptions import ImproperlyConfigured
from django.urls import include, path
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from drf_unified_rbac.authentication import KeycloakAuthentication
from drf_unified_rbac.authentication.adapters import BaseLocalAuthAdapter, DjangoLocalAuthAdapter
from drf_unified_rbac.conf import get_rbac_setting
from drf_unified_rbac.factories import get_local_auth_adapter
from drf_unified_rbac.models import Permission, Role, RolePermission, UserRole
from drf_unified_rbac.permissions import RBACPermission
from drf_unified_rbac.views import MeView

pytestmark = pytest.mark.django_db
LOGIN = '/api/rbac/auth/local/login'
LOGOUT = '/api/rbac/auth/local/logout'
CSRF = '/api/rbac/auth/local/csrf'
ME = '/api/rbac/me'


class Resource(APIView):
    authentication_classes = [KeycloakAuthentication, SessionAuthentication]
    permission_classes = [RBACPermission]
    required_permission = 'demo.local.view'

    def get(self, request):
        return Response({'ok': True})


urlpatterns = [
    path('api/rbac/', include('drf_unified_rbac.urls')),
    path('resource', Resource.as_view()),
]


class CustomAdapter(BaseLocalAuthAdapter):
    def authenticate(self, request, **credentials):
        assert request.path == LOGIN
        return auth.authenticate(request=request, **credentials)


class BrokenAdapter(BaseLocalAuthAdapter):
    def authenticate(self, request, **credentials):
        raise RuntimeError('secret-password-and-token')


class RejectedAdapter(BaseLocalAuthAdapter):
    def authenticate(self, request, **credentials):
        raise AuthenticationFailed('secret-password-and-token')


class BadConstructorAdapter(CustomAdapter):
    def __init__(self):
        raise RuntimeError('cannot construct')


class HostAuthentication(BaseAuthentication):
    user = None

    def authenticate(self, request):
        return self.user, None


@pytest.fixture
def client(settings, user):
    settings.ROOT_URLCONF = __name__
    settings.MIDDLEWARE = [
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
    ]
    role = Role.objects.create(code='local', name='Local')
    permission = Permission.objects.create(code='demo.local.view', name='Local')
    UserRole.objects.create(user=user, role=role)
    RolePermission.objects.create(role=role, permission=permission)
    return APIClient()


def login(client, **kwargs):
    return client.post(LOGIN, {'username': 'alice', 'password': 'unused'}, format='json', **kwargs)


@pytest.mark.parametrize('mode', ['local', 'hybrid'])
def test_login_me_allow_deny_logout(client, settings, mode):
    settings.DRF_RBAC = {'AUTH_MODE': mode}
    assert login(client).json() == {'authenticated': True}
    assert client.get(ME).json() == {
        'username': 'alice', 'auth_source': 'local',
        'roles': ['local'], 'permissions': ['demo.local.view'],
    }
    assert client.get('/resource').status_code == 200
    Permission.objects.update(enabled=False)
    assert client.get('/resource').status_code == 403
    assert client.post(LOGOUT).status_code == 204
    assert client.get(ME).status_code in (401, 403)
    assert client.get('/resource').status_code in (401, 403)
    assert '_auth_user_id' not in client.session


@pytest.mark.parametrize('data', [
    {'username': 'alice', 'password': 'wrong'},
    {'username': 'missing', 'password': 'unused'},
    {}, {'username': 'alice', 'password': ''},
    {'username': [], 'password': 1}, [],
])
def test_rejected_credentials_have_uniform_response(client, data):
    response = client.post(LOGIN, data, format='json')
    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication failed.'}
    assert '_auth_user_id' not in client.session


def test_inactive_user_cannot_login(client, user):
    user.is_active = False
    user.save()
    assert login(client).status_code == 401


@pytest.mark.parametrize('enabled', [True, False])
def test_existing_host_auth_never_calls_adapter(client, settings, monkeypatch, user, enabled):
    settings.DRF_RBAC = {'LOCAL_LOGIN_ENABLED': enabled, 'LOCAL_AUTH_ADAPTER': 'missing.Adapter'}
    monkeypatch.setattr(HostAuthentication, 'user', user)
    monkeypatch.setattr(MeView, 'authentication_classes', [HostAuthentication])
    monkeypatch.setattr(Resource, 'authentication_classes', [HostAuthentication])
    assert client.get(ME).json()['permissions'] == ['demo.local.view']
    assert client.get('/resource').status_code == 200
    if not enabled:
        for endpoint in (LOGIN, LOGOUT):
            assert client.post(endpoint).status_code == 404
        assert client.get(CSRF).status_code == 404


def test_disabled_login_preserves_existing_session(client, settings):
    assert login(client).status_code == 200
    settings.DRF_RBAC = {'LOCAL_LOGIN_ENABLED': False}
    assert client.post(LOGOUT).status_code == 404
    assert client.get(ME).json()['auth_source'] == 'local'
    assert client.get('/resource').status_code == 200


def test_sso_disables_package_local_endpoints(client, settings):
    settings.DRF_RBAC = {'AUTH_MODE': 'sso'}
    assert login(client).status_code == 404
    assert client.post(LOGOUT).status_code == 404


def test_custom_adapter_and_default_django_backend(client, settings):
    assert isinstance(get_local_auth_adapter(), DjangoLocalAuthAdapter)
    settings.DRF_RBAC = {'LOCAL_AUTH_ADAPTER': __name__ + '.CustomAdapter'}
    assert isinstance(get_local_auth_adapter(), CustomAdapter)
    assert login(client).status_code == 200
    assert client.get(ME).json()['auth_source'] == 'local'


@pytest.mark.parametrize('path', [
    'missing.Adapter', __name__ + '.Missing', __name__ + '.Resource',
    __name__ + '.BadConstructorAdapter',
    'drf_unified_rbac.authentication.adapters.BaseLocalAuthAdapter',
])
def test_broken_factory_fails_closed(client, settings, path):
    settings.DRF_RBAC = {'LOCAL_AUTH_ADAPTER': path}
    with pytest.raises(ImproperlyConfigured, match='LOCAL_AUTH_ADAPTER'):
        get_local_auth_adapter()
    with pytest.raises(ImproperlyConfigured):
        login(client)
    assert '_auth_user_id' not in client.session


@pytest.mark.parametrize('adapter', ['BrokenAdapter', 'RejectedAdapter'])
def test_adapter_exceptions_never_leak_credentials(client, settings, adapter, caplog):
    settings.DRF_RBAC = {'LOCAL_AUTH_ADAPTER': __name__ + '.' + adapter}
    response = login(client)
    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication failed.'}
    assert 'secret-password-and-token' not in caplog.text
    assert '_auth_user_id' not in client.session


@pytest.mark.parametrize('name,value', [
    ('LOCAL_AUTH_ADAPTER', None), ('LOCAL_AUTH_ADAPTER', 5),
    ('LOCAL_AUTH_ADAPTER', ''), ('LOCAL_AUTH_ADAPTER', 'missing'),
    ('LOCAL_LOGIN_ENABLED', 'False'), ('LOCAL_LOGIN_ENABLED', 0),
    ('LOCAL_LOGIN_ENABLED', None), ('AUTH_MODE', 'unknown'),
])
def test_invalid_config(settings, name, value):
    settings.DRF_RBAC = {name: value}
    with pytest.raises(ImproperlyConfigured):
        get_rbac_setting(name)


@pytest.mark.parametrize('header', ['Bearer invalid', 'Bearer', 'Bearer a b'])
def test_invalid_bearer_cannot_fall_back_to_active_session(
    client, settings, keycloak_config, stub_jwks, header,
):
    settings.DRF_RBAC = {**keycloak_config, 'AUTH_MODE': 'hybrid'}
    assert login(client).status_code == 200
    for url in (ME, '/resource'):
        assert client.get(url, HTTP_AUTHORIZATION=header).status_code == 401
    assert client.get(ME).json()['auth_source'] == 'local'


def test_valid_bearer_takes_precedence_without_merging_local_grants(
    client, settings, keycloak_config, stub_jwks, make_keycloak_token,
):
    settings.DRF_RBAC = {**keycloak_config, 'AUTH_MODE': 'hybrid'}
    role = Role.objects.create(code='sso', name='SSO')
    permission = Permission.objects.create(code='demo.sso.view', name='SSO')
    RolePermission.objects.create(role=role, permission=permission)
    assert login(client).status_code == 200
    token = make_keycloak_token(resource_access={'my-app': {'roles': ['sso']}})
    response = client.get(ME, HTTP_AUTHORIZATION='Bearer ' + token)
    assert response.status_code == 200
    assert response.json() == {'username': 'alice.sso', 'auth_source': 'sso',
                               'roles': ['sso'], 'permissions': ['demo.sso.view']}
    assert client.get('/resource', HTTP_AUTHORIZATION='Bearer ' + token).status_code == 403


@pytest.mark.parametrize('session_csrf', [False, True])
def test_real_csrf_login_rotation_and_logout(client, settings, session_csrf):
    settings.CSRF_USE_SESSIONS = session_csrf
    secure = APIClient(enforce_csrf_checks=True)
    assert login(secure).status_code == 403
    token = secure.get(CSRF).json()['csrfToken']
    assert login(secure, HTTP_X_CSRFTOKEN=token).status_code == 200
    assert secure.get(ME).status_code == 200
    assert secure.post(LOGOUT).status_code == 403
    assert secure.post(LOGOUT, HTTP_X_CSRFTOKEN=token).status_code == 403
    token = secure.get(CSRF).json()['csrfToken']
    assert secure.post(LOGOUT, HTTP_X_CSRFTOKEN=token).status_code == 204
    assert secure.get(ME).status_code in (401, 403)


def test_custom_authentication_backend_is_used(client, settings, monkeypatch, user):
    from django.contrib.auth.backends import ModelBackend
    calls = []

    def custom_authenticate(self, request, username=None, password=None, **kwargs):
        calls.append((request.path, username))
        return user if password == 'unused' else None

    monkeypatch.setattr(ModelBackend, 'authenticate', custom_authenticate)
    assert login(client).status_code == 200
    assert calls == [(LOGIN, 'alice')]
    assert client.get(ME).json()['username'] == 'alice'
