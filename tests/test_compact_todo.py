"""Tests for compact_todo helper — MCP response token efficiency."""
import json

from Omnispindle.tools import compact_todo, compact_todo_list


SAMPLE_TODO = {
    "_id": "6a1688c4c71b6c7a9939efd0",
    "id": "9fbe29b1-9f9c-481c-83a1-11b5e295dde5",
    "description": "fix the projects not selected bug",
    "project": "inventorium",
    "priority": "Medium",
    "status": "pending",
    "target": "user",
    "tags": ["bug-fix"],
    "created_at": 1779861700,
    "updated_at": 1779861713,
    "source": "personal",
    "metadata": {
        "created_by_ai": True,
        "user_id": "google-oauth2|115459928137014510094",
        "user_email": "danedens31@gmail.com",
        "chat_context": True,
        "tags": ["bug-fix"],  # duplicates top-level
        "complexity": "Medium",
        "blockers": ["abc-123"],
    },
    "notes": "Long multi-paragraph notes that bloat responses..." * 15,
}


def test_compact_always_strips_id_and_source():
    out = compact_todo(SAMPLE_TODO)
    assert "_id" not in out
    assert "source" not in out
    assert out["id"] == SAMPLE_TODO["id"]


def test_compact_strips_noise_metadata():
    out = compact_todo(SAMPLE_TODO)
    md = out["metadata"]
    for noise_key in ("user_id", "user_email", "created_by_ai", "chat_context"):
        assert noise_key not in md, f"{noise_key} should be stripped"
    # keep useful keys
    assert md["complexity"] == "Medium"
    assert md["blockers"] == ["abc-123"]


def test_compact_dedupes_metadata_tags():
    out = compact_todo(SAMPLE_TODO)
    # metadata.tags duplicates top-level tags → removed
    assert "tags" not in out.get("metadata", {})
    # top-level tags preserved
    assert out["tags"] == ["bug-fix"]


def test_compact_keeps_distinct_metadata_tags():
    doc = dict(SAMPLE_TODO)
    doc["metadata"] = dict(doc["metadata"])
    doc["metadata"]["tags"] = ["different", "tags"]
    out = compact_todo(doc)
    assert out["metadata"]["tags"] == ["different", "tags"]


def test_brief_strips_notes_and_updated_at():
    out = compact_todo(SAMPLE_TODO, brief=True)
    assert "notes" not in out
    assert "updated_at" not in out
    # essentials preserved
    assert out["description"] == SAMPLE_TODO["description"]
    assert out["status"] == "pending"


def test_brief_reduces_metadata_to_whitelist():
    out = compact_todo(SAMPLE_TODO, brief=True)
    md = out.get("metadata", {})
    # only blockers/files/complexity allowed in brief
    assert set(md.keys()) <= {"blockers", "files", "complexity"}
    assert md["blockers"] == ["abc-123"]
    assert md["complexity"] == "Medium"


def test_compact_todo_list_handles_none_entries():
    docs = [SAMPLE_TODO, None, dict(SAMPLE_TODO, id="other")]
    out = compact_todo_list(docs)
    assert len(out) == 2  # None dropped


def test_brief_response_is_substantially_smaller():
    full = json.dumps(compact_todo(SAMPLE_TODO))
    brief = json.dumps(compact_todo(SAMPLE_TODO, brief=True))
    # Brief should be at least 60% smaller given the bloated notes field
    assert len(brief) < len(full) * 0.4, f"brief={len(brief)} not much smaller than full={len(full)}"


def test_metadata_removed_when_empty_after_strip():
    doc = {
        "id": "x",
        "description": "test",
        "metadata": {"user_id": "noise", "user_email": "noise@x.com"},
    }
    out = compact_todo(doc)
    # all metadata keys stripped → metadata dropped entirely
    assert "metadata" not in out


def test_non_dict_passthrough():
    assert compact_todo("not a dict") == "not a dict"
    assert compact_todo(None) is None
