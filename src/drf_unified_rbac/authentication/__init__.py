__all__ = ["KeycloakAuthentication", "SSOUser"]


def __getattr__(name):
    # Local installations must not import the optional SSO dependency.
    if name in __all__:
        from . import keycloak
        return getattr(keycloak, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
