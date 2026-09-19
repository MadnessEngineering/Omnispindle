import os
import re
from typing import Optional, Dict, Any
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

# Load environment variables from .env file
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB", "swarmonomicon")  # Fallback/shared database


def sanitize_database_name(user_context: Dict[str, Any]) -> str:
    """
    Convert user context to a valid MongoDB database name.
    Prefers email over Auth0 'sub' for consistent database naming.
    MongoDB database names cannot contain certain characters.
    """
    # Prefer email as primary identifier (more stable than Auth0 sub)
    # This matches the Inventorium backend logic for consistency
    user_id = None
    if 'email' in user_context and user_context['email']:
        user_id = user_context['email']
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id).lower()
        database_name = f"user_{sanitized}"
        print(f"✅ Database naming: Using email: {user_id} -> {database_name}")
    elif 'sub' in user_context and user_context['sub']:
        user_id = user_context['sub']
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id).lower()
        database_name = f"user_{sanitized}"
        print(f"✅ Database naming: Using Auth0 sub: {user_id} -> {database_name}")
    else:
        # Fallback to shared database if no personal identifier available
        database_name = "swarmonomicon"
        user_info = user_context.get('id', 'unknown')
        print(f"⚠️ Database naming: No email or Auth0 sub found for user {user_info}")
        print(f"⚠️ Database naming: Using shared database: {database_name}")

    # MongoDB database names are limited to 64 characters
    if len(database_name) > 64:
        database_name = database_name[:64]

    return database_name


# ---------------------------------------------------------------------------
# Teams scope resolution — the Python MCP mirror of the Node backend's
# resolveScope + the assertNoTeamInProbeSet invariant (see TEAMS_AUDIT #13).
#
# sanitize_database_name only ever emits `user_<...>` or `swarmonomicon`, so a
# team database (`team_<slug>`) can NEVER be produced by the personal/shared
# path. A team scope is therefore reachable only through resolve_scope_collections,
# which verifies membership against `swarmonomicon.teams` BEFORE returning any
# handle. Everything here fails CLOSED: an unknown team, a non-member, a viewer
# writing, or a malformed token yields no team handle.
# ---------------------------------------------------------------------------

TEAM_SCOPE_PREFIX = "team:"


def is_team_database(name: Optional[str]) -> bool:
    """True for a team database (team_<slug>)."""
    return isinstance(name, str) and name.startswith("team_")


def parse_scope_token(scope: Optional[str]):
    """Normalize a client-supplied scope token to (kind, slug).

    None / '' / 'personal' -> ('personal', None)
    'shared' / 'swarmonomicon' -> ('shared', None)
    'team:<slug>' -> ('team', slug)

    Raises ValueError for a malformed team token ('team:'). Any other string
    falls back to ('personal', None) — never guess shared/team from junk.
    """
    if not scope:
        return ("personal", None)
    token = str(scope)
    if token in ("shared", "swarmonomicon"):
        return ("shared", None)
    if token.startswith(TEAM_SCOPE_PREFIX):
        slug = token[len(TEAM_SCOPE_PREFIX):]
        if not slug:
            raise ValueError("malformed team scope token")
        return ("team", slug)
    return ("personal", None)


def _member_candidate_ids(user_context: Optional[Dict[str, Any]]) -> set:
    """The identifiers a team member row may key on for this caller — mirrors the
    Node resolveTeamScope candidate set (sub / auth0Subject / id / email /
    'auth0|'+email)."""
    candidates = set()
    if not user_context:
        return candidates
    for key in ("sub", "auth0Subject", "id"):
        val = user_context.get(key)
        if val:
            candidates.add(val)
    email = user_context.get("email")
    if email:
        candidates.add(email)
        candidates.add(f"auth0|{email}")
    return candidates


def match_team_member(team_doc: Optional[Dict[str, Any]], user_context: Optional[Dict[str, Any]]):
    """Return the caller's member sub-doc within team_doc, or None.

    Fails CLOSED: a caller whose user_context carries email_verified == False is
    never matched (mirrors the Node require-on-true at the team boundary). When
    the flag is absent the identity came from a trusted server path (API key /
    get_current_user), so it is not re-litigated here.
    """
    if not team_doc or not user_context:
        return None
    if user_context.get("email_verified") is False:
        return None
    candidates = _member_candidate_ids(user_context)
    email = user_context.get("email")
    for member in (team_doc.get("members") or []):
        if member.get("sub") in candidates:
            return member
        if email and member.get("email") == email:
            return member
    return None


class Database:
    """A singleton class to manage MongoDB connections with user-scoped databases."""
    _instance = None
    client: MongoClient | None = None
    shared_db: MongoDatabase | None = None  # The original swarmonomicon database
    _user_databases: Dict[str, MongoDatabase] = {}  # Cache of user databases

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._user_databases = {}
            try:
                cls._instance.client = MongoClient(MONGODB_URI)
                # Ping the server to verify the connection
                cls._instance.client.admin.command('ping')
                print("MongoDB connection successful.")
            except Exception as e:
                print(f"Error connecting to MongoDB: {e}")
                cls._instance.client = None

            # Initialize shared database (legacy swarmonomicon)
            if cls._instance.client is not None:
                cls._instance.shared_db = cls._instance.client[MONGODB_DB_NAME]
            else:
                cls._instance.shared_db = None

        return cls._instance

    def get_user_database(self, user_context: Optional[Dict[str, Any]] = None) -> MongoDatabase:
        """
        Get the appropriate database for a user context.
        Returns user-specific database if user is authenticated, otherwise shared database.
        """
        if self.client is None:
            raise RuntimeError("MongoDB client not initialized")

        # If no user context, return shared database
        if not user_context:
            print("⚠️ Database routing: No user context provided, using shared database")
            return self.shared_db

        # Check for Auth0 'sub' field - the canonical user identifier
        if not user_context.get('sub'):
            user_info = user_context.get('email', user_context.get('id', 'unknown'))
            print(f"⚠️ Database routing: No Auth0 'sub' for user {user_info}, using shared database")
            return self.shared_db

        db_name = sanitize_database_name(user_context)

        # Return cached database if we have it
        if db_name in self._user_databases:
            return self._user_databases[db_name]

        # Create and cache new user database
        user_db = self.client[db_name]
        self._user_databases[db_name] = user_db

        user_id = user_context.get('sub', user_context.get('email', 'unknown'))
        print(f"✅ Database routing: Initialized user database: {db_name} for user {user_id}")
        return user_db

    def _collections_for_db(self, db: MongoDatabase) -> Dict[str, Collection]:
        """Build the standard collections dict for a resolved database handle."""
        collections_dict = {
            'todos': db["todos"],
            'deleted_todos': db["deleted_todos"],
            'lessons': db["lessons_learned"],
            'tags_cache': db["tags_cache"],
            'projects': db["projects"],
            'explanations': db["explanations"],
            'logs': db["todo_logs"],
            'quests': db["quests"]
        }
        # Add database reference for custom collection access
        collections_dict['database'] = db
        return collections_dict

    def get_collections(self, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Collection]:
        """
        Get all collections for the appropriate database (user-scoped or shared).

        Personal/shared ONLY. A team database must be resolved through
        resolve_scope_collections (membership-gated) — never here. The guard is
        belt-and-suspenders: get_user_database can't emit a team_ name today, so
        this only fires if that ever changes, and it fails CLOSED.
        """
        db = self.get_user_database(user_context)
        if is_team_database(getattr(db, "name", "")):
            raise PermissionError(
                "get_collections resolved a team database; use resolve_scope_collections (teams isolation invariant)"
            )
        return self._collections_for_db(db)

    def resolve_scope_collections(
        self,
        user_context: Optional[Dict[str, Any]],
        scope: Optional[str] = None,
        write: bool = False,
    ) -> Dict[str, Collection]:
        """
        Resolve a CLIENT-SUPPLIED scope token to a collections dict, membership-gated.
        The single place a scope string becomes trusted handles on the MCP side —
        the mirror of the Node resolveScope + scopedStore.

        scope: None / 'personal' -> caller's own DB; 'shared' / 'swarmonomicon' ->
        shared DB; 'team:<slug>' -> the team DB, but only if the caller is a member.

        Fails CLOSED. Raises PermissionError for a denied team scope, ValueError
        for a malformed token. Personal/shared behaviour is unchanged.
        """
        kind, slug = parse_scope_token(scope)
        if kind == "personal":
            return self.get_collections(user_context)
        if kind == "shared":
            return self.get_collections(None)

        # kind == 'team' — verify membership before returning any handle.
        if self.client is None or self.shared_db is None:
            raise PermissionError(f"cannot verify membership for team '{slug}' (no database)")
        team_doc = self.shared_db["teams"].find_one({"slug": slug})
        member = match_team_member(team_doc, user_context)
        if not member:
            raise PermissionError(f"not a member of team '{slug}'")
        if write and member.get("role") == "viewer":
            raise PermissionError(f"viewer cannot write to team '{slug}'")

        # db_name on the team doc is authoritative (schema D7). It MUST be a
        # team_ database; anything else is a misconfiguration — fail closed.
        db_name = team_doc.get("db_name")
        if not is_team_database(db_name):
            raise PermissionError(f"team '{slug}' has an invalid db_name")
        team_db = self.client[db_name]
        return self._collections_for_db(team_db)

    # Legacy properties for backward compatibility (use shared database)
    @property
    def db(self) -> MongoDatabase:
        """Legacy property - returns shared database"""
        return self.shared_db

    @property 
    def todos(self) -> Collection:
        """
        Legacy property for todos collection from shared database
        """
        return self.shared_db["todos"] if self.shared_db is not None else None

    @property
    def lessons(self) -> Collection:
        """
        Legacy property for lessons_learned collection from shared database
        """
        return self.shared_db["lessons_learned"] if self.shared_db is not None else None

    @property
    def tags_cache(self) -> Collection:
        """
        Legacy property for tags_cache collection from shared database
        """
        return self.shared_db["tags_cache"] if self.shared_db is not None else None

    @property
    def projects(self) -> Collection:
        """
        Legacy property for projects collection from shared database
        """
        return self.shared_db["projects"] if self.shared_db is not None else None
    
    @property
    def explanations(self) -> Collection:
        """
        Legacy property for explanations collection from shared database
        """
        return self.shared_db["explanations"] if self.shared_db is not None else None

    @property
    def logs(self) -> Collection:

        return self.shared_db["todo_logs"] if self.shared_db is not None else None


# Export a single instance for the application to use
db_connection = Database()
