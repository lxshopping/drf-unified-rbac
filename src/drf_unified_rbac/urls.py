from django.urls import path

from drf_unified_rbac.views import MeView


app_name = "drf_unified_rbac"

urlpatterns = [
    path("me", MeView.as_view(), name="me"),
]
