
from pydantic import BaseModel


class AuthConfig(BaseModel):
    """
    Pydantic model for Auth0 configuration.
    """
    domain: str
    audience: str
    client_id: str 
