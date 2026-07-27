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


# Description budget for search hits (chars). Descriptions were 62% of a
# search_todos payload — 10,732 of 17,306 chars on an 8-hit set — because a
# search result shipped every hit's full description even though only the
# matched span answers the query.
_DESC_TOTAL_BUDGET = 2400   # combined description text before snipping
_DESC_SNIPPET_MIN = 200     # a snippet below this says nothing useful


def _without_coordinates(items: list) -> list:
    """Drop coordinates from each item, top-level and under metadata.

    Coordinates are a SwarmDesk rendering blob ({x, y, z, lastUpdated} floats);
    a text search result has no use for them. Both spellings exist in the wild —
    the MCP tools write metadata.coordinates, the dashboard writes a top-level
    `coordinates` — and the top-level one is the common case (15 of 20 hits on a
    measured search, 8% of the payload). query_todos_near still returns them;
    that tool is the one asking a spatial question.
    """
    out = []
    for item in items:
        if not isinstance(item, dict):
            out.append(item)
            continue
        md = item.get("metadata")
        md_has = isinstance(md, dict) and "coordinates" in md
        if "coordinates" not in item and not md_has:
            out.append(item)
            continue
        item = {k: v for k, v in item.items() if k != "coordinates"}
        if md_has:
            md = {k: v for k, v in md.items() if k != "coordinates"}
            if md:
                item["metadata"] = md
            else:
                item.pop("metadata", None)
        out.append(item)
    return out


def _snip_descriptions(items: list, query: Optional[str]) -> tuple:
    """Cut oversized descriptions to a match-centred snippet. Returns (items, snipped)."""
    total = sum(len(i.get("description") or "") for i in items if isinstance(i, dict))
    if total <= _DESC_TOTAL_BUDGET:
        return items, False

    per_item = max(_DESC_SNIPPET_MIN, _DESC_TOTAL_BUDGET // len(items))
    tokens = [t.lower() for t in meaningful_tokens(query)] if query else []

    out, snipped = [], False
    for item in items:
        text = item.get("description") if isinstance(item, dict) else None
        if not text or len(text) <= per_item:
            out.append(item)
            continue
        item = dict(item)
        item["description"] = (
            _match_snippet(text, tokens, per_item)
            + f" [snippet — {len(text)} chars total, get_todo('{item.get('id', '')}') for full]"
        )
        out.append(item)
        snipped = True
    return out, snipped


def apply_response_diet(items: list, query: Optional[str] = None) -> tuple:
    """
    Auto-size a search result set so a fat corpus can't blow up context.

    Always     -> metadata.coordinates dropped (see _without_coordinates).
    Multi-hit  -> brief every item (notes dropped) once total notes exceed
                  _NOTES_TOTAL_BUDGET; oversized descriptions then cut to a
                  match-centred snippet once they exceed _DESC_TOTAL_BUDGET.
                  Small sets pass through whole.
    Single hit -> keep notes, truncated at _NOTES_SINGLE_HIT_BUDGET with a
                  pointer to get_todo for the rest.

    `query` centres the description snippet on the matched span, the same way
    apply_lesson_diet windows lesson_learned.

    Returns (items, diet) where diet is 'full' | 'brief' | 'truncated'. The label
    reports the *text* treatment: 'brief' means notes were dropped (descriptions
    may also be snipped), 'truncated' means text was cut but nothing dropped.
    """
    if not items:
        return items, "full"

    items = _without_coordinates(items)
    total_notes = sum(len(i.get("notes") or "") for i in items if isinstance(i, dict))

    if len(items) > 1:
        diet = "full"
        if total_notes > _NOTES_TOTAL_BUDGET:
            items = compact_todo_list(items, brief=True)
            diet = "brief"
        items, snipped = _snip_descriptions(items, query)
        if snipped and diet == "full":
            diet = "truncated"
        return items, diet

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


# Fields a fat list read keeps. Everything else — notes, prose metadata
# (current_state/target_state), timestamps, ticket, updated_by — is one
# get_todo away, and on a 10-item read it was 58% of the bytes.
_LIST_KEEP_FIELDS = ("id", "description", "project", "status", "priority", "tags")
_LIST_METADATA_KEEP = ("tags", "files")
_LIST_TOTAL_BUDGET = 4000   # trimmable chars across the set before slimming


def _trimmable_chars(item: dict) -> int:
    """Chars the list diet would remove from one item."""
    total = len(item.get("notes") or "")
    md = item.get("metadata")
    if isinstance(md, dict):
        total += sum(len(str(v)) for k, v in md.items() if k not in _LIST_METADATA_KEEP)
    return total


def apply_todo_list_diet(items: list) -> tuple:
    """
    Auto-size a plain list read (query_todos) — the browse-side sibling of
    apply_response_diet.

    A search hit is read once and discarded; a list read lands in the agent's
    window and stays there, so this cuts harder: past _LIST_TOTAL_BUDGET of
    trimmable text the set collapses to _LIST_KEEP_FIELDS plus metadata.tags /
    metadata.files. Measured 12,909 chars for limit=10 (4,873 metadata + 2,712
    notes) — ~345 tokens/todo where ~150 does the same job.

    Single-item and small sets pass through whole; the caller reaches for
    get_todo when it wants the rest.

    Returns (items, diet) where diet is 'full' | 'brief'.
    """
    if not items or len(items) < 2:
        return items, "full"

    trimmable = sum(_trimmable_chars(i) for i in items if isinstance(i, dict))
    if trimmable <= _LIST_TOTAL_BUDGET:
        return items, "full"

    out = []
    for item in items:
        if not isinstance(item, dict):
            out.append(item)
            continue
        slim = {k: item[k] for k in _LIST_KEEP_FIELDS if k in item}
        md = item.get("metadata")
        if isinstance(md, dict):
            kept = {k: md[k] for k in _LIST_METADATA_KEEP if md.get(k)}
            if kept:
                slim["metadata"] = kept
        out.append(strip_empty_fields(slim))
    return out, "brief"


def compact_log_entry(entry: dict) -> dict:
    """
    Audit-log mirror of compact_todo. get_logs stringifies Mongo's ObjectId into
    `_id` and hands the doc straight to the client — a 24-char field nothing
    downstream can look up, plus whatever empty fields the write left behind.
    """
    if not isinstance(entry, dict):
        return entry
    return strip_empty_fields({k: v for k, v in entry.items() if k != "_id"})


def compact_log_list(entries: list) -> list:
    """Apply compact_log_entry to each item in a list."""
    return [compact_log_entry(e) for e in entries if e]


def compact_stats_facets(stats: dict) -> dict:
    """
    Reshape a Mongo $facet aggregation for MCP.

    Every $group names its key `_id`, so a stats payload reads like a page of
    document ids. Rename to `value`, drop the null buckets (todos with no tag,
    no complexity, …), and flatten the single-element total_counts facet into a
    `totals` object — a single-item read returns the bare object, not a
    one-element list.
    """
    if not isinstance(stats, dict):
        return stats

    out = {}
    for key, bucket in stats.items():
        if key == "total_counts":
            continue
        if isinstance(bucket, list):
            out[key] = [
                {"value": b["_id"], **{k: v for k, v in b.items() if k != "_id"}}
                for b in bucket
                if isinstance(b, dict) and b.get("_id") is not None
            ]
        else:
            out[key] = bucket

    totals = stats.get("total_counts")
    if isinstance(totals, list) and totals and isinstance(totals[0], dict):
        out["totals"] = {k: v for k, v in totals[0].items() if k != "_id"}

    return strip_empty_fields(out)
