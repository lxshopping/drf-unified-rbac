from django.contrib import auth

from .base import BaseLocalAuthAdapter


class DjangoLocalAuthAdapter(BaseLocalAuthAdapter):
    """Delegate credential verification and backend selection to Django."""

    def authenticate(self, request, **credentials):
        return auth.authenticate(request=request, **credentials)
