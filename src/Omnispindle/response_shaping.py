"""
Shared response-shaping helpers for MCP payloads.

Lives outside tools.py so both the local (`tools.py`) and API (`api_tools.py`)
implementations use the same compaction rules — tools.py imports api_tools, so
anything api_tools needs from it has to live here to avoid an import cycle.
"""

from datetime import datetime, timezone
from typing import Optional


# Stop words stripped from tokenized/RAG searches to avoid matching on noise tokens.
# Also includes common dev-action verbs that appear in nearly every todo.
STOP_WORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "up", "about", "into", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "must",
    "and", "or", "but", "not", "no", "nor", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most", "some",
    "such", "than", "too", "very", "just", "also", "now", "then", "here",
    "there", "when", "where", "why", "how", "what", "which", "who", "whom",
    "this", "that", "these", "those", "it", "its", "my", "our", "your",
    "his", "her", "their", "i", "we", "you", "he", "she", "they", "me",
    "us", "him", "them", "if", "else", "while", "as", "until", "after",
    "before", "because", "since", "during", "without", "between", "through",
    "add", "fix", "update", "create", "remove", "change", "make", "get",
    "set", "use", "new", "existing",
})


def meaningful_tokens(query: str) -> list:
    """Split a query into search tokens, dropping stop words.

    Digits survive the length filter ("4", "2" are real queries). Falls back to
    the raw token list when every token is a stop word.
    """
    raw = [t for t in query.split() if t.strip()]
    filtered = [t for t in raw if t.lower() not in STOP_WORDS and (len(t) > 2 or t.isdigit())]
    return filtered if filtered else raw


# Helper function to strip empty fields to save tokens
def strip_empty_fields(obj):
    """Recursively remove empty fields (None, empty strings, empty lists, empty dicts)"""
    if isinstance(obj, dict):
        return {k: strip_empty_fields(v) for k, v in obj.items()
                if v not in (None, "", [], {})}
    elif isinstance(obj, list):
        return [strip_empty_fields(item) for item in obj if item not in (None, "", [], {})]
    return obj


# Metadata keys never useful to AI consumers — stripped from every MCP response
_AI_NOISE_METADATA_KEYS = {"user_id", "user_email", "created_by_ai", "chat_context"}

# Keys kept in compact metadata when brief mode is on
_BRIEF_METADATA_KEEP = {"blockers", "files", "complexity"}

# Epoch-second fields worth mirroring as human/AI-readable ISO on single-item reads
_TIMESTAMP_FIELDS = ("created_at", "updated_at", "completed_at")


def _iso_from_epoch(value) -> Optional[str]:
    """Render an epoch-seconds value as an ISO-8601 UTC string, or None if not epoch-like."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, OSError, OverflowError):
            return None
    return None


def compact_todo(doc: dict, brief: bool = False, iso_dates: bool = False) -> dict:
    """
    Reduce todo doc to MCP-friendly shape. Always: drop _id, drop per-doc source,
    drop empty fields (ticket: "", notes: "", [] and {}), strip noise metadata keys,
    dedupe metadata.tags against top-level tags.
    If brief=True: drop notes and reduce metadata to a small whitelist.
    If iso_dates=True: add *_iso mirrors of the epoch timestamps. Off by default —
    on a list response those extra fields multiply by N, so only single-item reads
    pay for readability.

    See compact_todo_list() for list-level handling (envelope source).
    """
    if not isinstance(doc, dict):
        return doc
    # Drop the search-only vector fields. The 768-float embedding is a RAG
    # index artifact — embeddings.find_similar reads it via its own projection
    # server-side; a client reading a todo has no use for it, and shipping it
    # inline bloated list payloads ~50x (a 30-item list ran ~80k tokens).
    out = {k: v for k, v in doc.items() if k not in ("_id", "source", "embedding", "embedding_updated_at")}

    md = out.get("metadata")
    if isinstance(md, dict):
        md = {k: v for k, v in md.items() if k not in _AI_NOISE_METADATA_KEYS}
        # Dedupe metadata.tags if it duplicates top-level tags
        if "tags" in md and md["tags"] == out.get("tags"):
            md.pop("tags", None)
        if brief:
            md = {k: v for k, v in md.items() if k in _BRIEF_METADATA_KEEP}
        if md:
            out["metadata"] = md
        else:
            out.pop("metadata", None)

    if brief:
        out.pop("notes", None)
        out.pop("updated_at", None)

    # Empty fields carry no information but cost tokens on every item (ticket: "",
    # notes: "", tags: []). Applied last so brief/metadata handling runs first.
    out = strip_empty_fields(out)

    if iso_dates:
        for field in _TIMESTAMP_FIELDS:
            if field in out:
                iso = _iso_from_epoch(out[field])
                if iso:
                    out[f"{field}_iso"] = iso
    return out


def compact_todo_list(docs: list, brief: bool = False, iso_dates: bool = False) -> list:
    """Apply compact_todo to each item in a list."""
    return [compact_todo(d, brief=brief, iso_dates=iso_dates) for d in docs if d]


# Fields kept when a lesson is requested in brief form
_BRIEF_LESSON_KEEP = ("id", "topic", "language", "tags")


def compact_lesson(doc: dict, brief: bool = False, iso_dates: bool = False) -> dict:
    """
    Lesson-side mirror of compact_todo. Lessons carry the same 768-float embedding
    as todos but never got the compaction treatment — get_lesson/list_lessons/
    search_lessons/grep_lessons returned raw Mongo docs, so a single lesson cost
    ~15KB of vector nobody reads (embeddings.find_similar loads it server-side via
    its own projection). Also drops _id and empty fields.
    """
    if not isinstance(doc, dict):
        return doc

    out = {k: v for k, v in doc.items() if k not in ("_id", "embedding", "embedding_updated_at")}

    if brief:
        out = {k: out[k] for k in _BRIEF_LESSON_KEEP if k in out}

    out = strip_empty_fields(out)

    if iso_dates:
        for field in _TIMESTAMP_FIELDS:
            if field in out:
                iso = _iso_from_epoch(out[field])
                if iso:
                    out[f"{field}_iso"] = iso
    return out


def compact_lesson_list(docs: list, brief: bool = False, iso_dates: bool = False) -> list:
    """Apply compact_lesson to each item in a list."""
    return [compact_lesson(d, brief=brief, iso_dates=iso_dates) for d in docs if d]


# Response-diet thresholds for search results (chars, roughly 4 chars/token)
_NOTES_SINGLE_HIT_BUDGET = 4000   # single hit: truncate notes past this
_NOTES_TOTAL_BUDGET = 2000        # multi hit: brief the whole set past this


def apply_response_diet(items: list) -> tuple:
    """
    Auto-size a search result set so a fat-notes corpus can't blow up context.

    Multi-hit  -> brief every item (notes dropped) once total notes exceed
                  _NOTES_TOTAL_BUDGET; small sets pass through whole.
    Single hit -> keep notes, truncated at _NOTES_SINGLE_HIT_BUDGET with a
                  pointer to get_todo for the rest.

    Returns (items, diet) where diet is 'full' | 'brief' | 'truncated'.
    """
    if not items:
        return items, "full"

    total_notes = sum(len(i.get("notes") or "") for i in items if isinstance(i, dict))

    if len(items) > 1:
        if total_notes > _NOTES_TOTAL_BUDGET:
            return compact_todo_list(items, brief=True), "brief"
        return items, "full"

    item = items[0]
    if isinstance(item, dict) and total_notes > _NOTES_SINGLE_HIT_BUDGET:
        item = dict(item)
        notes = item["notes"]
        item["notes"] = (
            notes[:_NOTES_SINGLE_HIT_BUDGET]
            + f"… [truncated — {len(notes)} chars total, get_todo('{item.get('id', '')}') for full]"
        )
        return [item], "truncated"
    return items, "full"


# Response-diet thresholds for lesson reads (chars, roughly 4 chars/token).
# lesson_learned is ~76% of a lesson payload's bytes, so it's the only field
# worth budgeting.
_LESSON_TOTAL_BUDGET = 6000       # multi hit: combined lesson_learned before snipping
_LESSON_SINGLE_HIT_BUDGET = 4000  # single hit: truncate lesson_learned past this
_LESSON_SNIPPET_MIN = 240         # a snippet below this says nothing useful


def _match_snippet(text: str, tokens: list, budget: int) -> str:
    """Window `budget` chars of `text` around the first token hit (head if none)."""
    start = 0
    if tokens:
        lowered = text.lower()
        hits = [p for p in (lowered.find(t) for t in tokens) if p >= 0]
        if hits:
            # Leave a third of the window as lead-in so the match has context.
            start = max(0, min(hits) - budget // 3)
    end = start + budget
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def apply_lesson_diet(items: list, query: Optional[str] = None) -> tuple:
    """
    Auto-size a lesson result set — lesson-side mirror of apply_response_diet,
    budgeting lesson_learned instead of notes.

    Multi-hit  -> once combined lesson_learned exceeds _LESSON_TOTAL_BUDGET,
                  every oversized lesson_learned is cut to a match-relevant
                  snippet sized budget/len(items); small sets pass through whole.
    Single hit -> keeps lesson_learned, truncated at _LESSON_SINGLE_HIT_BUDGET
                  with a pointer to get_lesson for the rest.

    Where the todo diet briefs notes away, this snips instead: lesson_learned IS
    the answer, so dropping it would force a get_lesson round-trip on every hit.

    Returns (items, diet) where diet is 'full' | 'truncated'.
    """
    if not items:
        return items, "full"

    total = sum(len(i.get("lesson_learned") or "") for i in items if isinstance(i, dict))

    if len(items) > 1:
        if total <= _LESSON_TOTAL_BUDGET:
            return items, "full"

        per_item = max(_LESSON_SNIPPET_MIN, _LESSON_TOTAL_BUDGET // len(items))
        tokens = [t.lower() for t in meaningful_tokens(query)] if query else []

        out = []
        for item in items:
            text = item.get("lesson_learned") if isinstance(item, dict) else None
            if not text or len(text) <= per_item:
                out.append(item)
                continue
            item = dict(item)
            item["lesson_learned"] = (
                _match_snippet(text, tokens, per_item)
                + f" [snippet — {len(text)} chars total, get_lesson('{item.get('id', '')}') for full]"
            )
            out.append(item)
        return out, "truncated"

    item = items[0]
    if isinstance(item, dict) and total > _LESSON_SINGLE_HIT_BUDGET:
        item = dict(item)
        text = item["lesson_learned"]
        item["lesson_learned"] = (
            text[:_LESSON_SINGLE_HIT_BUDGET]
            + f"… [truncated — {len(text)} chars total, get_lesson('{item.get('id', '')}') for full]"
        )
        return [item], "truncated"
    return items, "full"
