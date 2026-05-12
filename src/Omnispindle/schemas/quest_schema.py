"""
Pydantic schemas for Quest — epic containers for todo chains
with agent check-in progress tracking.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class QuestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ABANDONED = "abandoned"


class ChainStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class QuestChain(BaseModel):
    """A named sequence (or parallel group) of todos within a quest."""
    model_config = ConfigDict(extra="allow")

    label: str = Field(..., description="Chain name, e.g. 'tag-enforcement'")
    todos: List[str] = Field(default_factory=list, description="Ordered list of todo UUIDs")
    parallel: bool = Field(default=False, description="If true, todos run in parallel (after gate)")
    gate_todo: Optional[str] = Field(default=None, description="UUID that must complete before parallel todos unlock")
    status: ChainStatus = Field(default=ChainStatus.PENDING)

    @field_validator('todos')
    @classmethod
    def validate_todos(cls, v):
        if v is not None:
            return [t.strip() for t in v if t and t.strip()]
        return v


class QuestSchema(BaseModel):
    """Core quest document schema."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="UUID v4 identifier")
    name: str = Field(..., max_length=200, description="Quest name")
    description: str = Field(..., max_length=2000, description="Goal statement")
    project: str = Field(..., description="Project scope")
    status: QuestStatus = Field(default=QuestStatus.ACTIVE)
    created_at: int = Field(..., description="Unix timestamp")
    updated_at: int = Field(..., description="Unix timestamp")
    completed_at: Optional[int] = Field(default=None)
    success_criteria: List[str] = Field(default_factory=list)
    chains: List[QuestChain] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()

    @field_validator('project')
    @classmethod
    def validate_project(cls, v):
        if not v or not v.strip():
            raise ValueError('project cannot be empty')
        return v.lower().strip()


class QuestCreateRequest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    project: str
    chains: List[QuestChain] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class QuestUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[QuestStatus] = None
    success_criteria: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
