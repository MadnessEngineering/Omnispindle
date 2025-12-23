"""
Authentication utilities shared between stdio and HTTP servers.
"""

import os
import httpx
import json
import time
from jose import jwt
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()
logger = logging.getLogger(__name__)

# JWKS caching to avoid fetching on every token verification
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_time: Optional[float] = None
_jwks_ttl = 3600  # 1 hour TTL for JWKS keys

# Reusable HTTP client for Auth0 requests
_http_client: Optional[httpx.AsyncClient] = None


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
    """
    Fetches JWKS from Auth0 with caching.

    Performance optimization: JWKS keys don't change often, so we cache them
    with a 1-hour TTL to avoid remote HTTP calls on every token verification.
    This reduces latency from 1-2 seconds to ~0ms for cached requests.
    """
    global _jwks_cache, _jwks_cache_time, _http_client

    # Check cache first
    now = time.time()
    if _jwks_cache is not None and _jwks_cache_time is not None:
        cache_age = now - _jwks_cache_time
        if cache_age < _jwks_ttl:
            logger.debug(f"⚡ Using cached JWKS (age: {cache_age:.1f}s)")
            return _jwks_cache

    # Cache miss or expired - fetch fresh JWKS
    logger.info(f"🔄 Fetching fresh JWKS from Auth0 (cache {'expired' if _jwks_cache else 'empty'})")
    start_time = time.time()

    jwks_url = f"https://{AUTH_CONFIG.domain}/.well-known/jwks.json"

    # Reuse HTTP client for connection pooling
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)

    response = await _http_client.get(jwks_url)
    response.raise_for_status()

    # Update cache
    _jwks_cache = response.json()
    _jwks_cache_time = now

    fetch_time = time.time() - start_time
    logger.info(f"✅ JWKS fetched in {fetch_time:.3f}s, cached for {_jwks_ttl}s")

    return _jwks_cache


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