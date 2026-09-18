from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_unified_rbac.domain import Principal
from drf_unified_rbac.conf import get_rbac_setting
from drf_unified_rbac.services import get_authorization_service


class MeView(APIView):
    """Expose the authenticated identity and its current RBAC grants."""

    permission_classes = [IsAuthenticated]

    def get_authenticators(self):
        authenticators = super().get_authenticators()
        if get_rbac_setting("AUTH_MODE") in ("sso", "hybrid"):
            from drf_unified_rbac.authentication import KeycloakAuthentication
            # Validate any Keycloak Bearer before a host session can succeed.
            authenticators = [KeycloakAuthentication()] + [
                item for item in authenticators if not isinstance(item, KeycloakAuthentication)
            ]
        return authenticators

    def get(self, request):
        try:
            principal = Principal.from_user(request.user)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PermissionDenied("Invalid authenticated identity.") from exc
        service = get_authorization_service()
        return Response(
            {
                "username": principal.username,
                "auth_source": principal.auth_source,
                "roles": sorted(service.get_roles(principal)),
                "permissions": sorted(service.get_permissions(principal)),
            }
        )
