import os
import json
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt, JWTError
from urllib.request import urlopen

# Fetch Auth0 configuration from environment variables
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
API_AUDIENCE = os.environ.get("API_AUDIENCE")
ALGORITHMS = ["RS256"]

# A simple cache for Auth0's JSON Web Key Set (JWKS)
_jwks = None

class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extracts the JWT from the 'ss-tok' cookie."""
    return request.cookies.get("ss-tok")

async def get_current_user(
    request: Request,
    token_from_cookie: Optional[str] = Depends(get_token_from_cookie),
    # The default security scheme will try to get the token from the Authorization header
    token_from_header: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False)),
    ) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current user from a JWT.
    It checks for a token in the 'ss-tok' cookie (for browsers) and the
    'Authorization' header (for other clients).
    """
    token = token_from_cookie or token_from_header
    if token is None:
        raise AuthError(detail="Authentication token is missing.", status_code=status.HTTP_401_UNAUTHORIZED)

    global _jwks
    if _jwks is None:
        jsonurl = urlopen(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        _jwks = json.loads(jsonurl.read())

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise AuthError(detail="Invalid token header")

    rsa_key = {}
    for key in _jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
            break

    if not rsa_key:
        raise AuthError(detail="Unable to find the appropriate key")

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=API_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
        return payload
    # except jwt.ExpiredSignatureError:
    #     raise AuthError(detail="Token has expired")
    # except jwt.JWTClaimsError as e:
    #     raise AuthError(detail=f"Invalid claims: {e}")
    except Exception as e:
        raise AuthError(detail=f"Unable to parse authentication token: {e}")
