"""Tests for MCP HTTP transport response encoding — no double-JSON-encoding.

Tools in tools.py already return JSON strings. The /api/mcp handler used to run
json.dumps() over that string again, producing a JSON string literal with every
quote escaped (~10-15% token overhead) and forcing clients to parse twice.
"""
import json

from Omnispindle.mcp_handler import _as_text


SAMPLE_PAYLOAD = {
    "id": "9fbe29b1-9f9c-481c-83a1-11b5e295dde5",
    "description": "fix the projects not selected bug",
    "project": "inventorium",
    "status": "pending",
    "metadata": {"tags": ["bug-fix"], "complexity": "Medium"},
}


def test_json_string_passes_through_unescaped():
    tool_result = json.dumps(SAMPLE_PAYLOAD)
    text = _as_text(tool_result)

    assert text == tool_result
    assert '\\"' not in text
    # A single parse yields the payload, not another string
    assert json.loads(text) == SAMPLE_PAYLOAD


def test_non_json_string_passes_through():
    assert _as_text("plain message") == "plain message"


def test_dict_is_serialized_once():
    text = _as_text(SAMPLE_PAYLOAD)
    assert json.loads(text) == SAMPLE_PAYLOAD


def test_non_serializable_falls_back_to_str():
    class Opaque:
        def __str__(self):
            return "opaque"

    assert json.loads(_as_text({"x": Opaque()})) == {"x": "opaque"}


def test_single_encoding_is_smaller_than_double_encoding():
    tool_result = json.dumps(SAMPLE_PAYLOAD)
    double_encoded = json.dumps(tool_result, default=str)

    assert len(_as_text(tool_result)) < len(double_encoded)
