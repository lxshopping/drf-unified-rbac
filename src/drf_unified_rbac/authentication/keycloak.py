from rest_framework.authentication import BaseAuthentication, get_authorization_header

class KetcloakAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            return None

        if auth[0].lower() != b'bearer':
            return None

        if len(auth) != 2:
            raise AuthenticationFailed(
                'Invalid token header. No credentials provided.')

        token = auth[1].decode()

        token = self.get_bearer_token(request)

        signing_key = self.get_keycloak_signing_key(token)

        claims = jwt.decode(token, signing_key, algorithms=['RS256'],issuser=KEYCLOAK_ISSUER,audience=KEYCLOAK_CLIENT_ID)

        user = SSOUser(claims)

        return (user, claims)

    
            

class SSOUser:
    def __init__(self, claims):
        self.subject = claims["sub"]
        self.username = claims["preferred_username"]

    @property
    def is_authenticated(self):
        return True

    def get_username(self):
        return self.username