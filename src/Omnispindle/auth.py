
import json
import logging
from functools import lru_cache
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt
from jose.exceptions import JWTError

from Omnispindle.models.config import AuthConfig

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

AUTH_CONFIG = AuthConfig(
    domain="dev-eoi0koiaujjbib20.us.auth0.com",
    audience="https://madnessinteractive.cc/api",
    client_id="U43kJwbd1xPcCzJsu3kZIIeNV1ygS7x1",
)


@lru_cache(maxsize=1)
def get_jwks():
    """
    Fetches the JSON Web Key Set (JWKS) from the Auth0 domain.
    The result is cached to avoid repeated HTTP requests.
    """
    try:
        url = f"https://{AUTH_CONFIG.domain}/.well-known/jwks.json"
        with httpx.Client() as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error requesting JWKS: {e}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching JWKS: {e.response.status_code} - {e.response.text}")
        raise


async def get_current_user(security_scopes: SecurityScopes, token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    """
    Dependency to get the current user from the Auth0-signed JWT.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    unverified_header = jwt.get_unverified_header(token)
    jwks = get_jwks()
    rsa_key = {}
    for key in jwks["keys"]:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH_CONFIG.audience,
            issuer=f"https://{AUTH_CONFIG.domain}/",
        )
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if security_scopes.scopes:
        token_scopes = set(payload.get("scope", "").split())
        if not token_scopes.issuperset(set(security_scopes.scopes)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return payload


async def get_current_user_from_query(token: str) -> Optional[dict]:
    """
    A dependency that extracts the user from a token passed as a query parameter.
    Used for streaming endpoints where headers might not be as convenient.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing from query.",
        )
    # Re-use the same logic as the header-based dependency
    return await get_current_user(SecurityScopes([]), token)
