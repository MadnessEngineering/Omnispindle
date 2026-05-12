"""
Canonical tag taxonomy — single source of truth for tag enforcement.

All valid tags are lowercase-hyphenated. RETIRED_TO_CANONICAL maps
niche/retired variants to their canonical replacement. Used by:
  - todo_metadata_schema.py (Pydantic validator, Phase 3)
  - http_server.py (tool docstring injection, Phase 1)
  - deep_merge_metadata $push path (Phase 4)
"""

CANONICAL_TAGS: frozenset = frozenset({
    # Domain
    "ui", "frontend", "backend", "swarmdesk", "mcp", "api",
    "auth", "ai", "chat", "database", "omnispindle",
    # Work type
    "enhancement", "bugfix", "bug", "cleanup", "refactor",
    "automation", "tooling", "testing", "docs", "planning",
    "wip", "audit",
    # Quality
    "security", "performance", "data-quality", "code-quality", "monitoring",
    # Features
    "theme", "locales", "translations", "deployment", "git", "hooks",
    "eaws", "mobile", "three.js", "floating-panels", "hotkeys",
    "uml", "chronomancy", "todos", "agents", "visualization", "mindmap",
    # Phases (pattern: phase-N)
    "phase-1", "phase-2", "phase-3", "phase-4",
})


RETIRED_TO_CANONICAL: dict[str, str] = {
    # Component/scope consolidation
    "floating-panel": "floating-panels",
    "dead-code": "cleanup",
    "dead-code-removal": "cleanup",
    "localstorage": "frontend",
    "components": "frontend",
    # Naming normalization
    "test": "testing",
    "metadata": "data-quality",
    "history": "docs",
    "refactoring": "refactor",
    "bug-fix": "bugfix",
    "authentication": "auth",
    "documentation": "docs",
    # Theme/translation aliases
    "theming": "theme",
    "themes": "theme",
    "translation": "locales",
    "i18n": "locales",
    # Hotkey aliases
    "hotkey": "hotkeys",
    "keybinds": "hotkeys",
    # 3D/SwarmDesk aliases
    "three-js": "three.js",
    "3d-positioning": "swarmdesk",
    "district-zones": "swarmdesk",
    # MCP aliases
    "mcp-tool": "mcp",
    "mcp-tools": "mcp",
    # Phase formatting
    "phase1": "phase-1",
    "phase2": "phase-2",
    "phase3": "phase-3",
    "phase4": "phase-4",
    # Todo aliases
    "todolist": "todos",
    "todo-list": "todos",
    "todo": "todos",
    # Casing
    "ui": "ui",
    # Tech debt
    "tech-debt": "refactor",
    "technical-debt": "refactor",
    # Performance
    "preload": "performance",
}


def normalize_tag(tag: str) -> str:
    """Normalize a single tag: lowercase, retire-to-canonical, strip whitespace."""
    tag = tag.lower().strip()
    return RETIRED_TO_CANONICAL.get(tag, tag)


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalize and deduplicate a list of tags."""
    seen = set()
    result = []
    for tag in tags:
        normalized = normalize_tag(tag)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def format_tag_guidance() -> str:
    """Generate condensed tag guidance string for tool docstrings."""
    sorted_tags = sorted(CANONICAL_TAGS)
    return (
        "Tags: lowercase+hyphens only, min 3 tags. "
        f"Canonical set: {', '.join(sorted_tags)}. "
        "Phases: phase-N (hyphenated). "
        "Retired aliases auto-normalize on write."
    )
