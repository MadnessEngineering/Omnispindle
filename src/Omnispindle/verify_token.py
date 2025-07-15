import json
from urllib.request import urlopen
from jose import jwt

class VerifyToken:
    """Does all the token verification using PyJWT"""

    def __init__(self, auth0_domain, api_audience):
        self.auth0_domain = auth0_domain
        self.api_audience = api_audience
        self.jwks = None

    def verify(self, token):
        self._get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = self._find_rsa_key(unverified_header)

        if rsa_key:
            return jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=self.api_audience,
                issuer=f"https://{self.auth0_domain}/"
            )
        raise Exception("Unable to find appropriate key")

    def _get_jwks(self):
        if self.jwks is None:
            jsonurl = urlopen(f"https://{self.auth0_domain}/.well-known/jwks.json")
            self.jwks = json.loads(jsonurl.read())

    def _find_rsa_key(self, unverified_header):
        for key in self.jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        return None 
