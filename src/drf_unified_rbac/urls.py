from django.urls import include, path

from drf_unified_rbac.views import MeView
from drf_unified_rbac.authentication.views import LocalCSRFView, LocalLoginView, LocalLogoutView


app_name = "drf_unified_rbac"

urlpatterns = [
    path("auth/local/csrf", LocalCSRFView.as_view(), name="local-csrf"),
    path("auth/local/login", LocalLoginView.as_view(), name="local-login"),
    path("auth/local/logout", LocalLogoutView.as_view(), name="local-logout"),
    path("admin/", include("drf_unified_rbac.admin_api.urls")),
    path("me", MeView.as_view(), name="me"),
]
