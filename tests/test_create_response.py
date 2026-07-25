"""Tests for create_response envelope — no redundant agent_context block."""
import json

from Omnispindle.utils import create_response


def test_no_agent_context_block():
    out = json.loads(create_response(True, {"todo_id": "abc-123", "description": "d"}))
    assert "agent_context" not in out


def test_entity_id_hoisted_to_top_level():
    out = json.loads(create_response(True, {"todo_id": "abc-123"}))
    assert out["todo_id"] == "abc-123"
    assert out["success"] is True
    assert out["data"] == {"todo_id": "abc-123"}
    # id appears exactly twice (hoisted + inside data), not three times as before
    assert create_response(True, {"todo_id": "abc-123"}).count("abc-123") == 2


def test_lesson_entity_id_hoisted():
    out = json.loads(create_response(True, {"lesson_id": "les-1"}))
    assert out["lesson_id"] == "les-1"


def test_failure_response_is_minimal():
    out = json.loads(create_response(False, message="Todo not found"))
    assert out == {"success": False, "message": "Todo not found"}


def test_failure_does_not_hoist_id():
    out = json.loads(create_response(False, {"todo_id": "abc-123"}, "nope"))
    assert "todo_id" not in out
    assert out["data"] == {"todo_id": "abc-123"}


def test_collection_response_has_no_context():
    out = json.loads(create_response(True, {"items": [{"description": "a"}], "count": 1}))
    assert "agent_context" not in out
    assert out["data"]["count"] == 1


def test_data_omitted_when_none():
    assert json.loads(create_response(True)) == {"success": True}
