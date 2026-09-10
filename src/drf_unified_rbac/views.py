from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.services import get_authorization_service


class MeView(APIView):
    """Expose the authenticated identity and its current RBAC grants."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        principal = Principal.from_user(request.user)
        service = get_authorization_service()
        return Response(
            {
                "username": principal.username,
                "auth_source": principal.auth_source,
                "roles": sorted(service.get_roles(principal)),
                "permissions": sorted(service.get_permissions(principal)),
            }
        )
