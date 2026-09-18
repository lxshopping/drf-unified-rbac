from abc import ABC, abstractmethod


class BaseLocalAuthAdapter(ABC):
    """Validate login credentials, never resolve authorization grants.

    Return a Django session-compatible local user, or None on rejection.
    With multiple backends the returned user must carry its Django backend path.
    AuthenticationFailed is also supported; its detail is hidden by the endpoint.
    """

    @abstractmethod
    def authenticate(self, request, **credentials):
        raise NotImplementedError
