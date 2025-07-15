import logging
from dataclasses import dataclass
from typing import List, Optional

from fastapi import Cookie, Header, HTTPException, Request, Response, status
from jose import jwt
from pydantic import Field
from pydantic_settings import BaseSettings

from .verify_token import VerifyToken

logger = logging.getLogger(__name__)

@dataclass
class CurrentUser:
    """Represents the currently authenticated user."""
    name: str
    permissions: List[str]

class Settings(BaseSettings):
    """Auth settings for the application, loaded from environment variables."""
    enabled: bool = Field(default=True, env="AUTH_ENABLED")
    testing: bool = Field(default=False, env="TESTING")
    domain: str = Field(default="", env="AUTH0_DOMAIN")
    api_audience: str = Field(default="", env="AUTH0_API_AUDIENCE")
    issuer: str = Field(default="", env="AUTH0_ISSUER")
    algorithms: list[str] = Field(default_factory=lambda: ["RS256"], env="AUTH0_ALGORITHMS")

async def get_current_user(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(default=None),
    ss_tok: Optional[str] = Cookie(default=None),
    ) -> CurrentUser:
    """
    FastAPI dependency to get the current user from a JWT.
    The token can be provided in the Authorization header or in a secure, HttpOnly cookie.
    In testing mode, a special 'let-me-in' token is accepted.
    """
    auth_config = Settings()
    if not auth_config.enabled:
        return CurrentUser(name="local_dev_user", permissions=["*"])

    token = ss_tok or (authorization.split(" ")[1] if authorization and " " in authorization else None)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if auth_config.testing and token == "let-me-in":
        logger.info("Granting access to test user via magic token.")
        return CurrentUser(name="local_test_user", permissions=["*"])

    try:
        verify_token = VerifyToken(auth_config.domain, auth_config.api_audience)
        payload = verify_token.verify(token)
        # The 'sub' claim from Auth0 JWT is the user's unique ID.
        # We can use it as the user name.
        user_name = payload.get("sub", "unknown_user")
        permissions = payload.get("permissions", [])
        return CurrentUser(name=user_name, permissions=permissions)
    except Exception as e:
        logger.error(f"Token validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
