# Todo Metadata Standards Analysis

## Current State Analysis

Based on review of existing todo entries in the collection, here are the metadata patterns found:

## Core Fields (Standardized)
These fields appear consistently across all todos:

```json
{
  "_id": "ObjectId",
  "id": "uuid-v4-string",
  "description": "string",
  "project": "string",
  "priority": "High|Medium|Low|Critical",
  "status": "pending|completed|in_progress",
  "target_agent": "user|claude|system",
  "created_at": "unix_timestamp",
  "updated_at": "unix_timestamp"
}
```

## Completion Fields (When status=completed)
```json
{
  "completed_at": "unix_timestamp",
  "duration": "human_readable_string", // e.g. "1 minute"
  "duration_sec": "number_of_seconds"
}
```

## Metadata Field Variations Found

### Pattern 1: Phase-Based Metadata (Most Common)
Used in omnispindle todos for grouping related tasks:
```json
"metadata": {
  "phase": "pm2-modernization|docker-update|...",
  "file": "path/to/file.ext",
  "completed_by": "email_address",
  "completion_comment": "detailed_completion_notes"
}
```

### Pattern 2: Technical State Tracking
From your example in the conversation:
```json
"metadata": {
  "file": "src/Omnispindle/stdio_server.py",
  "current_state": "hardcoded_all_tools",
  "needed": "respect_OMNISPINDLE_TOOL_LOADOUT"
}
```

### Pattern 3: Feature Development Metadata
From inventorium todos:
```json
"metadata": {
  "component": "TodoList Integration",
  "file": "src/components/TodoList.jsx",
  "changes": "170+ lines modified",
  "features": ["field validation", "MCP updates", "real-time saving", "TTS integration"],
  "completed_by": "email_address",
  "completion_comment": "detailed_notes"
}
```

### Pattern 4: Task Analysis Metadata
Current analysis task:
```json
"metadata": {
  "task_type": "analysis",
  "deliverable": "todo_metadata_standards.md",
  "scope": "review_existing_formats_and_standardize"
}
```

## Identified Issues & Inconsistencies

### 1. Field Naming Variations
- `target_agent` vs `target` (some todos use `target`)
- `completed_by` appears in metadata vs potential top-level field
- `completion_comment` in metadata vs potential standardized field

### 2. Data Type Inconsistencies
- Some timestamps as unix timestamps, others as ISO strings
- Duration stored as both human-readable strings and seconds
- Arrays vs comma-separated strings for lists

### 3. Missing Structure
- No validation schema for metadata contents
- Free-form metadata leads to inconsistent structures
- No standardized way to represent file references, dependencies, or relationships

## Proposed Standardization

### Core Schema (Mandatory)
```json
{
  "_id": "ObjectId",
  "id": "uuid-v4",
  "description": "string (required, max 500 chars)",
  "project": "string (required, from approved project list)",
  "priority": "Critical|High|Medium|Low (required)",
  "status": "pending|in_progress|completed|blocked (required)",
  "target_agent": "user|claude|system (required)",
  "created_at": "unix_timestamp (auto-generated)",
  "updated_at": "unix_timestamp (auto-updated)"
}
```

### Completion Fields (When status=completed)
```json
{
  "completed_at": "unix_timestamp",
  "completed_by": "email_or_agent_id",
  "completion_comment": "string (optional)",
  "duration_sec": "number (calculated)"
}
```

### Standardized Metadata Schema
```json
"metadata": {
  // Technical Context (optional)
  "files": ["array", "of", "file/paths"],
  "components": ["ComponentName1", "ComponentName2"],
  "commit_hash": "string (optional)",
  "branch": "string (optional)",

  // Project Organization (optional)
  "phase": "string (for multi-phase projects)",
  "epic": "string (for grouping related features)",
  "tags": ["tag1", "tag2", "tag3"],

  // State Tracking (optional)
  "current_state": "string (what exists now)",
  "target_state": "string (desired end state) (or epic-todo uuid)",
  "blockers": ["blocker1-uuid", "blocker2-uuid"],

  // Deliverables (optional)
  "deliverables": ["file1.md", "component.jsx"],
  "acceptance_criteria": ["criteria1", "criteria2"],

  // Analysis & Estimates (optional)
  "complexity": "Low|Medium|High|Complex",
  "confidence": "1|2|3|4|5",

  // Custom fields (project-specific)
  "custom": {
    // Project-specific metadata goes here
  }
}
```

## Implementation Recommendations

### Phase 1: Immediate Standardization
1. Standardize core fields naming (`target_agent` over `target`)
2. Move `completed_by` and `completion_comment` to top level, including updating Inventorium to use the new fields
3. Ensure all timestamps use unix format
4. Add validation for required fields

### Phase 2: Metadata Migration
1. Create migration script to standardize existing metadata
2. Convert string arrays to proper arrays
3. Normalize file path references
4. Add missing completion tracking fields

### Phase 3: Enhanced Features
1. Add dependency tracking between todos
2. Implement epic/phase grouping
3. Add estimation and complexity tracking
4. Create metadata validation schemas

### Phase 4: Integration Improvements
1. Auto-populate file references from git changes
2. Link todos to commits/branches
3. Add integration with project management tools
4. Implement todo templates for common patterns

## Form Design Recommendations

For the metadata form in todo creation:

### Basic Tab
- Core fields (description, project, priority, target_agent)
- Phase/Epic selection (dropdown with project-specific options)
- Tags (multi-select or chip input)

### Technical Tab (Optional)
- File references (file picker or manual entry)
- Component names (autocomplete from project)
- Dependencies (todo picker)
- Current/Target state (text areas)

### Planning Tab (Optional)
- Estimated hours (number input)
- Complexity level (radio buttons)
- Acceptance criteria (dynamic list)
- Deliverables (file list)

This structure provides consistency while maintaining flexibility for different project needs.
