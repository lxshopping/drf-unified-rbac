from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from demo.views import DemoOrderViewSet


router = DefaultRouter()
router.register("orders", DemoOrderViewSet, basename="order")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/rbac/", include("drf_unified_rbac.urls")),
    path("api/", include(router.urls)),
]
