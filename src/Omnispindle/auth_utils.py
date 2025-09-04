"""
Authentication utilities shared between stdio and HTTP servers.
"""

import os
import httpx
import json
from jose import jwt
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class Auth0Config:
    domain: str
    client_id: str
    audience: str


# Auth0 configuration
AUTH_CONFIG = Auth0Config(
    domain=os.getenv("AUTH0_DOMAIN", "dev-eoi0koiaujjbib20.us.auth0.com"),
    client_id=os.getenv("AUTH0_CLIENT_ID", "U43kJwbd1xPcCzJsu3kZIIeNV1ygS7x1"),
    audience=os.getenv("AUTH0_AUDIENCE", "https://madnessinteractive.cc/api")
)


async def get_jwks() -> Dict[str, Any]:
    """Fetches JWKS from Auth0."""
    jwks_url = f"https://{AUTH_CONFIG.domain}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        return response.json()


async def verify_auth0_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies an Auth0 token and returns the payload."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = await get_jwks()
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
            logger.error("Unable to find appropriate key in JWKS")
            return None

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH_CONFIG.audience,
            issuer=f"https://{AUTH_CONFIG.domain}/",
        )
        return payload

    except jwt.ExpiredSignatureError:
        logger.error("JWT Error: Signature has expired.")
        return None
    except jwt.JWTClaimsError as e:
        logger.error(f"JWT Error: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT Verification Error: {e}")
        return None