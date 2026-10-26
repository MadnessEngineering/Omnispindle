from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from pymongo import MongoClient


@dataclass
class Context:
    """
    A context object to hold request-specific state that can be passed through the system.
    This helps avoid passing multiple arguments through function calls and provides a consistent
    way to access common objects like database connections or user information.
    """
    user: Optional[Dict[str, Any]] = None
    database: Optional[MongoClient] = None
    # You can add other request-scoped objects here, e.g., logger, settings
    metadata: Dict[str, Any] = field(default_factory=dict)
    # The caller's raw bearer credential (an 'omni_...' API key or an Auth0 JWT), for tools that call
    # the Inventorium REST API AS the caller (api_tools: sessions, world). Kept OUT of `user` because
    # `user` is handed to loggers and activity records; repr=False so printing a Context never shows it.
    # Set by the remote JSON-RPC handler on tools/call. Never log or store this.
    credential: Optional[str] = field(default=None, repr=False)
