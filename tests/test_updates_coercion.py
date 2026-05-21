"""
Tests for _normalize_updates helper and string-payload coercion in update functions.

Validates that update_todo, update_lesson, and update_explanation all handle
JSON string payloads gracefully (coercing to dict) rather than iterating characters
or passing raw strings to MongoDB $set.
"""
import os

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "test_swarmonomicon")
os.environ.setdefault("MONGODB_COLLECTION", "test_todos")

import json
import pytest
from src.Omnispindle.tools import _normalize_updates


# ── Unit tests for _normalize_updates ──────────────────────────────────────


class TestNormalizeUpdates:
    def test_dict_passthrough(self):
        result, err = _normalize_updates({"status": "in_progress"})
        assert err is None
        assert result == {"status": "in_progress"}

    def test_valid_json_string(self):
        result, err = _normalize_updates('{"status": "in_progress"}')
        assert err is None
        assert result == {"status": "in_progress"}

    def test_invalid_json_string(self):
        result, err = _normalize_updates("not json at all")
        assert result is None
        assert "must be a dict or valid JSON" in err

    def test_json_array_string_rejected(self):
        """JSON array parses fine but isn't a dict — should fail."""
        result, err = _normalize_updates('[1, 2, 3]')
        assert result is None
        assert "must be a dict" in err

    def test_list_rejected(self):
        result, err = _normalize_updates([1, 2, 3])
        assert result is None
        assert "must be a dict" in err

    def test_int_rejected(self):
        result, err = _normalize_updates(42)
        assert result is None
        assert "must be a dict" in err

    def test_none_rejected(self):
        result, err = _normalize_updates(None)
        assert result is None
        assert "must be a dict" in err

    def test_empty_dict(self):
        result, err = _normalize_updates({})
        assert err is None
        assert result == {}

    def test_empty_json_string(self):
        result, err = _normalize_updates('{}')
        assert err is None
        assert result == {}

    def test_custom_label_in_error(self):
        _, err = _normalize_updates("bad", label="lesson_updates")
        assert "lesson_updates" in err

    def test_nested_dict_string(self):
        """Nested JSON objects should parse correctly."""
        payload = '{"metadata": {"pr": "42", "blockers": []}}'
        result, err = _normalize_updates(payload)
        assert err is None
        assert result == {"metadata": {"pr": "42", "blockers": []}}
