"""Standalone consumer check: no username field, UUID pk, host login contract."""
from io import StringIO

from django.conf import settings

settings.configure(
    SECRET_KEY="custom-user-test", USE_TZ=True, ALLOWED_HOSTS=["testserver"],
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes",
                    "django.contrib.sessions", "rest_framework", "tests.custom_user_app", "drf_unified_rbac"],
    MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware"],
    AUTH_USER_MODEL="custom_user_app.User",
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    ROOT_URLCONF="tests.test_admin_api", DRF_RBAC={"AUTH_MODE": "local"},
)
import django
django.setup()

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient
from drf_unified_rbac.admin_api.serializers import LocalUserSerializer
from drf_unified_rbac.models import Role, UserRole

call_command("migrate", run_syncdb=True, verbosity=0)
model = get_user_model()
user = model.objects.create(login="operator@example.test")
other = model.objects.create(login="other@example.test")
call_command("rbac_bootstrap_admin", username=user.login, stdout=StringIO())
call_command("rbac_bootstrap_admin", username=user.login, stdout=StringIO())
assert model.objects.count() == 2 and UserRole.objects.count() == 1
client = APIClient()
client.force_authenticate(user)
me = client.get("/api/rbac/me")
assert me.status_code == 200 and me.json()["roles"] == ["rbac_admin"]
assert me.json()["username"] == user.login
users = client.get("/api/rbac/admin/users/", {"search": "operator@"}).json()
assert users["count"] == 1
assert users["results"] == [{"id": str(user.pk), "username": user.login, "is_active": True}]
endpoint = f"/api/rbac/admin/users/{other.pk}/roles/"
assert client.put(endpoint, {"role_codes": ["rbac_admin"]}, format="json").status_code == 200
assert client.get(endpoint).json() == {"role_codes": ["rbac_admin"]}
assert UserRole.objects.filter(user=other, role__code="rbac_admin").exists()
assert client.get("/api/rbac/admin/users/not-a-uuid/roles/").status_code == 404
assert client.put("/api/rbac/admin/users/not-a-uuid/roles/", {"role_codes": []}, format="json").status_code == 404
# A host user object need not expose is_active for safe serialization.
from types import SimpleNamespace
minimal = SimpleNamespace(pk="custom-id", get_username=lambda: "minimal")
assert LocalUserSerializer(minimal).data == {"id": "custom-id", "username": "minimal"}
print("Custom user: UUID pk, USERNAME_FIELD search, bootstrap, me and role assignment passed.")

# V3 default adapter must restore a UUID/email user through real Django Session.
user.set_password("custom-user-password")
user.save()
session_client = APIClient()
response = session_client.post("/api/rbac/auth/local/login", {
    "username": user.login, "password": "custom-user-password",
}, format="json")
assert response.status_code == 200, response.content
me = session_client.get("/api/rbac/me")
assert me.status_code == 200 and me.json()["username"] == user.login
assert me.json()["permissions"]
assert session_client.post("/api/rbac/auth/local/logout").status_code == 204
assert session_client.get("/api/rbac/me").status_code in (401, 403)
