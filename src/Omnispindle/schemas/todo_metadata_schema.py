"""
Pydantic schemas for todo metadata validation following the standardized schema.
Based on the Inventorium standardization requirements.
"""

import json
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum

from ..config.canonical_tags import normalize_tags


class PriorityLevel(str, Enum):
    """Valid priority levels for todos."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Synonyms / loose forms the AI (or a human) may emit, mapped to canonical labels.
# Case-insensitive; unknown values fall back to "Medium" (the historical default).
_PRIORITY_ALIASES = {
    "critical": "Critical", "crit": "Critical", "urgent": "Critical",
    "blocker": "Critical", "p0": "Critical",
    "high": "High", "hi": "High", "h": "High", "p1": "High",
    "medium": "Medium", "med": "Medium", "normal": "Medium",
    "m": "Medium", "p2": "Medium", "default": "Medium",
    "low": "Low", "lo": "Low", "l": "Low", "p3": "Low", "minor": "Low",
}


def normalize_priority(value: Optional[str]) -> str:
    """Map any case/synonym form of a priority to its canonical label.

    Fixes AI-supplied 'low'/'LOW' silently reading as Medium downstream because
    the UI matches the canonical 'Low' exactly. Unknown -> 'Medium'.
    """
    if not value:
        return PriorityLevel.MEDIUM.value
    return _PRIORITY_ALIASES.get(str(value).strip().lower(), PriorityLevel.MEDIUM.value)


class StatusLevel(str, Enum):
    """Valid status levels for todos."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ComplexityLevel(str, Enum):
    """Valid complexity levels for metadata."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    COMPLEX = "Complex"


# Story-point equivalents for the t-shirt sizes agents actually send. 32 live todos
# carry 'xs'/'s'/'m'/'l' in a field typed as an int 1-10 — the sizes are the de-facto
# vocabulary, so translate rather than refuse. Module scope, not class scope: pydantic
# turns a leading-underscore class attribute into a ModelPrivateAttr.
EFFORT_SIZES = {'xs': 1, 's': 2, 'sm': 2, 'm': 3, 'md': 3, 'l': 5, 'lg': 5,
                'xl': 8, 'xxl': 13}


class TodoMetadata(BaseModel):
    """
    Standardized metadata schema for todos.

    This schema enforces the standardized metadata structure agreed upon
    between Omnispindle and Inventorium for consistent todo management.
    """

    model_config = ConfigDict(extra="allow")  # Allow arbitrary custom fields

    # Technical Context (optional)
    files: Optional[List[str]] = Field(default=None, description="Array of file paths related to this todo")
    components: Optional[List[str]] = Field(default=None, description="Component names (e.g., ComponentName1, ComponentName2)")
    commit_hash: Optional[str] = Field(default=None, description="Git commit hash if applicable")
    branch: Optional[str] = Field(default=None, description="Git branch name if applicable")
    
    # Project Organization (optional)
    phase: Optional[str] = Field(default=None, description="Phase identifier for multi-phase projects")
    epic: Optional[str] = Field(default=None, description="Epic identifier for grouping related features")
    tags: Optional[List[str]] = Field(default=None, description="Array of tags for categorization")
    
    # State Tracking (optional)
    current_state: Optional[str] = Field(default=None, description="Description of current state")
    target_state: Optional[str] = Field(default=None, description="Desired end state or epic-todo UUID")
    blockers: Optional[List[str]] = Field(default=None, description="Array of blocker todo UUIDs")
    
    # Deliverables (optional)
    deliverables: Optional[List[str]] = Field(default=None, description="Expected deliverable files/components")
    acceptance_criteria: Optional[List[str]] = Field(default=None, description="Acceptance criteria for completion")
    
    # Spatial / SwarmDesk (optional)
    district: Optional[str] = Field(default=None, description="SwarmDesk district label (e.g. 'core', 'rag', 'ui', 'infra', 'npc-brain')")
    effort: Optional[int] = Field(default=None, ge=1, le=10, description="Effort estimate in story points (1-10)")
    coordinates: Optional[Dict[str, float]] = Field(default=None, description="Semantic 3D position {x, y, z} for SwarmDesk layout. Agents assign based on topic proximity.")

    # Analysis & Estimates (optional)
    complexity: Optional[ComplexityLevel] = Field(default=None, description="Complexity assessment")
    confidence: Optional[int] = Field(default=None, ge=1, le=5, description="Confidence level (1-5)")
    
    # Custom fields (project-specific)
    custom: Optional[Dict[str, Any]] = Field(default=None, description="Project-specific metadata")
    
    # Legacy fields (maintained for backward compatibility)
    completed_by: Optional[str] = Field(default=None, description="Email or agent ID of completer")
    completion_comment: Optional[str] = Field(default=None, description="Comments on completion")
    
    @field_validator('files', 'components', 'blockers', 'tags', mode='before')
    @classmethod
    def coerce_token_list_fields(cls, v):
        """
        Accept a string where a list of TOKENS belongs, and split it on commas.

        Agents send these as CSV or as JSON text often enough that rejecting the
        value costs more than coercing it. Rejection is not a safe failure here:
        add_todo and update_todo catch a validation error and store the RAW
        metadata anyway with a _validation_warning, so a refused string is written
        through unchanged — which is how a todo ended up carrying

            metadata.files: 'test_suites/regression_ed_serial.py, serial_replay.py, …'

        and crashed Inventorium's review queue at `.map`, since a string answers
        `.length` and `.slice()` exactly like a list and only fails there.

        Splitting on commas is safe HERE and only here: paths, tags, component
        names and uuids do not contain commas. Prose fields get the separate
        validator below, because a criterion routinely does.

        A dict is the other shape in the wild — agents group paths by intent,
        {'create': [...], 'modify': [...], 'reference': [...]} — so flatten its
        values rather than discarding real paths.

        Runs in 'before' mode so it lands ahead of pydantic's list type check;
        validate_arrays below then cleans the result as usual.
        """
        if isinstance(v, dict):
            flat = []
            for group in v.values():
                if isinstance(group, list):
                    flat.extend(group)
                elif isinstance(group, str) and group.strip():
                    flat.append(group.strip())
            return flat
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            # A JSON array arrives as text from some callers; fall back to CSV.
            if text.startswith('['):
                try:
                    decoded = json.loads(text)
                    if isinstance(decoded, list):
                        return decoded
                except (ValueError, TypeError):
                    pass
            return [part.strip() for part in text.split(',') if part.strip()]
        return v

    @field_validator('deliverables', 'acceptance_criteria', mode='before')
    @classmethod
    def coerce_prose_list_fields(cls, v):
        """
        Same rescue as the token fields, with the opposite comma rule.

        These hold sentences, and sentences contain commas. 12 live todos carry a
        single criterion as a bare string:

            'CLAUDE.md updated with architecture summary, commands section, …'

        Splitting that on commas does not produce three criteria, it produces
        three fragments — so a lone string becomes ONE item. A JSON array in text
        form is still honoured, since that is unambiguous.

        A dict of grouped prose flattens to its values, mirroring the token
        validator above ({'file_consolidation_map': '90+ files mapped…'} is real).
        """
        if isinstance(v, dict):
            flat = []
            for group in v.values():
                if isinstance(group, list):
                    flat.extend(group)
                elif isinstance(group, str) and group.strip():
                    flat.append(group.strip())
            return flat
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            if text.startswith('['):
                try:
                    decoded = json.loads(text)
                    if isinstance(decoded, list):
                        return decoded
                except (ValueError, TypeError):
                    pass
            # Newlines and bullets DO separate criteria; commas do not.
            parts = [p.strip().lstrip('-•* ').strip() for p in text.splitlines()]
            parts = [p for p in parts if p]
            return parts if len(parts) > 1 else [text]
        return v

    @field_validator('effort', mode='before')
    @classmethod
    def coerce_effort(cls, v):
        """Accept a t-shirt size or a numeric string where story points belong."""
        if isinstance(v, str):
            text = v.strip().lower()
            if not text:
                return None
            if text in EFFORT_SIZES:
                return EFFORT_SIZES[text]
            try:
                return int(float(text))
            except (ValueError, TypeError):
                return None   # unusable rather than written through raw
        return v

    @field_validator('phase', mode='before')
    @classmethod
    def coerce_phase(cls, v):
        """A phase identifier is a label; agents send the number 3 as often as '3'."""
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        return v

    @field_validator('files', 'components', 'deliverables', 'acceptance_criteria', 'blockers')
    @classmethod
    def validate_arrays(cls, v):
        """Ensure arrays don't contain empty strings."""
        if v is not None:
            return [item for item in v if item and item.strip()]
        return v

    @field_validator('tags')
    @classmethod
    def validate_and_normalize_tags(cls, v):
        """Normalize tags: lowercase, retire-to-canonical, deduplicate."""
        if v is not None:
            cleaned = [item for item in v if item and item.strip()]
            return normalize_tags(cleaned)
        return v
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        """Validate confidence is between 1-5."""
        if v is not None and (v < 1 or v > 5):
            raise ValueError('confidence must be between 1 and 5')
        return v


class TodoSchema(BaseModel):
    """
    Core todo schema with standardized fields.
    """
    
    # Core required fields
    id: str = Field(..., description="UUID v4 identifier")
    description: str = Field(..., max_length=500, description="Todo description (max 500 chars)")
    project: str = Field(..., description="Project name from approved project list")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Priority level")
    status: StatusLevel = Field(default=StatusLevel.PENDING, description="Current status")
    target_agent: str = Field(default="user", description="Target agent (user|claude|system)")
    
    # Timestamps (auto-managed)
    created_at: int = Field(..., description="Unix timestamp of creation")
    updated_at: Optional[int] = Field(default=None, description="Unix timestamp of last update")
    
    # Completion fields (when status=completed)
    completed_at: Optional[int] = Field(default=None, description="Unix timestamp of completion")
    completed_by: Optional[str] = Field(default=None, description="Email or agent ID of completer")
    completion_comment: Optional[str] = Field(default=None, description="Comments on completion")
    duration_sec: Optional[int] = Field(default=None, description="Duration in seconds from creation to completion")
    
    # Standardized metadata
    metadata: Optional[TodoMetadata] = Field(default_factory=dict, description="Structured metadata")
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Ensure description is not empty."""
        if not v or not v.strip():
            raise ValueError('description cannot be empty')
        return v.strip()
    
    @field_validator('project')
    @classmethod
    def validate_project(cls, v):
        """Validate project name format."""
        if not v or not v.strip():
            raise ValueError('project cannot be empty')
        # Convert to lowercase for consistency
        return v.lower().strip()


class TodoCreateRequest(BaseModel):
    """Schema for creating a new todo."""
    description: str = Field(..., max_length=500)
    project: str
    priority: PriorityLevel = PriorityLevel.MEDIUM
    target_agent: str = "user"
    metadata: Optional[TodoMetadata] = None


class TodoUpdateRequest(BaseModel):
    """Schema for updating an existing todo."""
    description: Optional[str] = Field(default=None, max_length=500)
    project: Optional[str] = None
    priority: Optional[PriorityLevel] = None
    status: Optional[StatusLevel] = None
    target_agent: Optional[str] = None
    metadata: Optional[TodoMetadata] = None
    completed_by: Optional[str] = None
    completion_comment: Optional[str] = None


def validate_todo_metadata(metadata: Dict[str, Any]) -> TodoMetadata:
    """
    Validate and normalize todo metadata.
    
    Args:
        metadata: Raw metadata dictionary
        
    Returns:
        Validated TodoMetadata instance
        
    Raises:
        ValidationError: If metadata doesn't meet schema requirements
    """
    return TodoMetadata(**metadata)


def validate_todo(todo_data: Dict[str, Any]) -> TodoSchema:
    """
    Validate and normalize a complete todo object.
    
    Args:
        todo_data: Raw todo dictionary
        
    Returns:
        Validated TodoSchema instance
        
    Raises:
        ValidationError: If todo doesn't meet schema requirements
    """
    return TodoSchema(**todo_data)


# Export validation functions for easy import
__all__ = [
    'TodoMetadata',
    'TodoSchema', 
    'TodoCreateRequest',
    'TodoUpdateRequest',
    'PriorityLevel',
    'StatusLevel',
    'ComplexityLevel',
    'validate_todo_metadata',
    'validate_todo'
]