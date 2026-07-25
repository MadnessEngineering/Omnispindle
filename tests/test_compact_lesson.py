"""Tests for compact_lesson — lessons used to ship their 768-float embedding."""
import json
import re

from Omnispindle.response_shaping import compact_lesson, compact_lesson_list


SAMPLE_LESSON = {
    "_id": "6a1688c4c71b6c7a9939efd0",
    "id": "3c2b1a09-0000-4000-8000-abcdefabcdef",
    "language": "python",
    "topic": "MCP double-encoding",
    "lesson_learned": "Tool results are already JSON strings; don't dumps() them again.",
    "tags": ["mcp", "serialization"],
    "created_at": 1779861700,
    "embedding": [0.0123] * 768,
    "embedding_updated_at": 1779861713,
}


def test_embedding_is_dropped():
    out = compact_lesson(SAMPLE_LESSON)
    assert "embedding" not in out
    assert "embedding_updated_at" not in out


def test_mongo_id_is_dropped():
    assert "_id" not in compact_lesson(SAMPLE_LESSON)


def test_content_survives():
    out = compact_lesson(SAMPLE_LESSON)
    assert out["id"] == SAMPLE_LESSON["id"]
    assert out["topic"] == SAMPLE_LESSON["topic"]
    assert out["lesson_learned"] == SAMPLE_LESSON["lesson_learned"]
    assert out["tags"] == ["mcp", "serialization"]


def test_empty_fields_stripped():
    doc = {"id": "x", "topic": "t", "language": "", "tags": [], "lesson_learned": "body"}
    out = compact_lesson(doc)
    assert "language" not in out and "tags" not in out
    assert out["lesson_learned"] == "body"


def test_brief_reduces_to_whitelist():
    out = compact_lesson(SAMPLE_LESSON, brief=True)
    assert set(out.keys()) <= {"id", "topic", "language", "tags"}
    assert "lesson_learned" not in out


def test_brief_tolerates_missing_fields():
    out = compact_lesson({"id": "x"}, brief=True)
    assert out == {"id": "x"}


def test_iso_dates_mirror_epoch():
    out = compact_lesson(SAMPLE_LESSON, iso_dates=True)
    assert out["created_at"] == SAMPLE_LESSON["created_at"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", out["created_at_iso"])


def test_non_dict_passthrough():
    assert compact_lesson("not a dict") == "not a dict"
    assert compact_lesson(None) is None


def test_list_drops_none_entries():
    assert len(compact_lesson_list([SAMPLE_LESSON, None])) == 1


def test_compaction_is_dramatically_smaller():
    raw = json.dumps(SAMPLE_LESSON, default=str)
    compacted = json.dumps(compact_lesson(SAMPLE_LESSON))
    # 768 floats dominate the raw doc
    assert len(compacted) < len(raw) * 0.1
