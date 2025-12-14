
import json
import logging
from functools import lru_cache
from typing import Optional
from datetime import datetime
import bcrypt
import os
import asyncio

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt
from jose.exceptions import JWTError

from .models.config import AuthConfig

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

AUTH_CONFIG = AuthConfig(
    domain="dev-eoi0koiaujjbib20.us.auth0.com",
    audience="https://madnessinteractive.cc/api",
    client_id="U43kJwbd1xPcCzJsu3kZIIeNV1ygS7x1",
)

async def verify_api_key(api_key: str) -> Optional[dict]:
    """
    Verify an API key against user databases and return user info
    Searches across all user databases since API keys are stored per-user
    """
    try:
        # Import here to avoid circular imports
        from .database import db_connection

        # Get MongoDB client to access all databases
        client = db_connection.client

        # Get list of user databases (databases starting with 'user_')
        database_names = client.list_database_names()
        user_databases = [name for name in database_names if name.startswith('user_')]

        logger.info(f"🔑 Searching for API key across {len(user_databases)} user databases")

        # Search each user database for the API key
        for db_name in user_databases:
            try:
                user_db = client[db_name]
                api_keys_collection = user_db['api_keys']

                # Find active, non-expired API keys in this user's database
                active_keys = list(api_keys_collection.find({
                    'is_active': True,
                    'expires_at': {'$gt': datetime.utcnow()}
                }))

                # Check each key against the provided key using bcrypt
                for key_record in active_keys:
                    if bcrypt.checkpw(api_key.encode('utf-8'), key_record['key_hash'].encode('utf-8')):
                        # Update last_used timestamp in a separate thread (non-blocking)
                        def update_last_used():
                            api_keys_collection.update_one(
                                {'key_id': key_record['key_id']},
                                {'$set': {'last_used': datetime.utcnow()}}
                            )

                        # Run the update in background
                        asyncio.create_task(asyncio.to_thread(update_last_used))

                        logger.info(f"🔑 API key verified for user: {key_record['user_email']} in database: {db_name}")

                        # Return user-like object compatible with Auth0 format
                        return {
                            'sub': key_record['user_id'],
                            'email': key_record['user_email'],
                            'name': key_record['user_email'],
                            'auth_method': 'api_key',
                            'key_id': key_record['key_id'],
                            'key_name': key_record['name'],
                            'user_database': db_name,  # Include which database this user uses
                            # Add scope for compatibility
                            'scope': 'read:todos write:todos'
                        }

            except Exception as db_error:
                # Log but continue - some user databases might have issues
                logger.debug(f"Error checking database {db_name}: {db_error}")
                continue

        logger.warning("❌ Invalid API key attempted - not found in any user database")
        return None

    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return None


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
    Dependency to get the current user from Auth0 JWT or API key.
    Falls back to API key verification if JWT validation fails.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if this is an API key (starts with omni_)
    if token.startswith('omni_'):
        logger.info("🔑 Attempting API key authentication")
        user_info = await verify_api_key(token)
        if user_info:
            # Check scopes if required
            if security_scopes.scopes:
                token_scopes = set(user_info.get("scope", "").split())
                if not token_scopes.issuperset(set(security_scopes.scopes)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            return user_info
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Try JWT validation for Auth0 tokens
    try:
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

    except JWTError as jwt_error:
        # If JWT fails and it's not an API key, try API key verification as fallback
        logger.warning(f"JWT validation failed, trying API key fallback: {jwt_error}")
        user_info = await verify_api_key(token)
        if user_info:
            logger.info("🔑 Successfully authenticated via API key fallback")
            # Check scopes if required
            if security_scopes.scopes:
                token_scopes = set(user_info.get("scope", "").split())
                if not token_scopes.issuperset(set(security_scopes.scopes)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            return user_info
        else:
            # Neither JWT nor API key worked
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )


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
