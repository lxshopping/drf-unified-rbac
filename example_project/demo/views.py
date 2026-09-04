from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from drf_unified_rbac.permissions import RBACPermission


class DemoOrderViewSet(ViewSet):
    permission_classes = [RBACPermission]
    required_permissions = {
        "list": "demo.order.view",
        "create": "demo.order.create",
        "approve": "demo.order.approve",
        "destroy": "demo.order.delete",
    }

    def list(self, request):
        return Response({"orders": []})

    def create(self, request):
        return Response(
            {"message": "order created"},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def approve(self, request):
        return Response({"message": "order approved"})


    def destroy(self, request, pk=None):
        return Response(
            {"message": f"order {pk} deleted"},
            status=status.HTTP_204_NO_CONTENT
            )