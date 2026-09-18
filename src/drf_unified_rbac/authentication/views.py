import logging
from collections.abc import Mapping

from django.contrib import auth
from django.middleware.csrf import get_token
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_unified_rbac.conf import get_rbac_setting
from drf_unified_rbac.domain import Principal
from drf_unified_rbac.factories import get_local_auth_adapter

logger = logging.getLogger(__name__)


class LocalAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        if get_rbac_setting("AUTH_MODE") == "sso" or not get_rbac_setting("LOCAL_LOGIN_ENABLED"):
            raise NotFound()
        super().initial(request, *args, **kwargs)
        # DRF's SessionAuthentication skips CSRF for anonymous users. Login and
        # logout must enforce it even before a session has been authenticated.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            SessionAuthentication().enforce_csrf(request)


class LocalCSRFView(LocalAuthView):
    """Bootstrap CSRF for API-only clients, including CSRF_USE_SESSIONS hosts."""

    def get(self, request):
        response = Response({"csrfToken": get_token(request._request)})
        response["Cache-Control"] = "no-store"
        return response


class LocalLoginView(LocalAuthView):
    def post(self, request):
        # The public endpoint accepts the default username/password contract.
        # Custom adapters can translate it; direct adapter callers may pass
        # additional credentials accepted by their Django backend.
        data = request.data
        if not isinstance(data, Mapping) or any(
            not isinstance(data.get(key), str) or not data[key]
            for key in ("username", "password")
        ):
            return Response({"detail": "Authentication failed."}, status=401)
        adapter = get_local_auth_adapter()
        try:
            user = adapter.authenticate(
                request._request, username=data["username"], password=data["password"]
            )
            if user is None:
                raise AuthenticationFailed()
            Principal.from_local_user(user)
            if not getattr(user, "is_active", True):
                raise AuthenticationFailed()
        except AuthenticationFailed:
            return Response({"detail": "Authentication failed."}, status=401)
        except Exception as exc:
            # Exception text may contain credentials supplied by a custom adapter.
            logger.error("Local authentication adapter failed (%s)", type(exc).__name__)
            return Response({"detail": "Authentication failed."}, status=401)
        try:
            auth.login(request._request, user)
        except Exception as exc:
            # A backend/session failure must never leave a partly logged-in session.
            auth.logout(request._request)
            logger.error("Local session login failed (%s)", type(exc).__name__)
            return Response({"detail": "Authentication failed."}, status=401)
        return Response({"authenticated": True})


class LocalLogoutView(LocalAuthView):
    def post(self, request):
        auth.logout(request._request)
        return Response(status=204)
