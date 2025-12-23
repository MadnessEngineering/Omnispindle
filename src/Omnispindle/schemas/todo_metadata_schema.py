"""
Pydantic schemas for todo metadata validation following the standardized schema.
Based on the Inventorium standardization requirements.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum


class PriorityLevel(str, Enum):
    """Valid priority levels for todos."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


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
    
    # Analysis & Estimates (optional)
    complexity: Optional[ComplexityLevel] = Field(default=None, description="Complexity assessment")
    confidence: Optional[int] = Field(default=None, ge=1, le=5, description="Confidence level (1-5)")
    
    # Custom fields (project-specific)
    custom: Optional[Dict[str, Any]] = Field(default=None, description="Project-specific metadata")
    
    # Legacy fields (maintained for backward compatibility)
    completed_by: Optional[str] = Field(default=None, description="Email or agent ID of completer")
    completion_comment: Optional[str] = Field(default=None, description="Comments on completion")
    
    @validator('files', 'components', 'deliverables', 'acceptance_criteria', 'tags', 'blockers')
    def validate_arrays(cls, v):
        """Ensure arrays don't contain empty strings."""
        if v is not None:
            return [item for item in v if item and item.strip()]
        return v
    
    @validator('confidence')
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
    
    @validator('description')
    def validate_description(cls, v):
        """Ensure description is not empty."""
        if not v or not v.strip():
            raise ValueError('description cannot be empty')
        return v.strip()
    
    @validator('project')
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