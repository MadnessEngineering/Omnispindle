"""Tests for api_tools.search_todos — two-pass matching + response diet in API mode."""
import asyncio
import json

import pytest

from Omnispindle import api_tools


class _FakeResponse:
    def __init__(self, data):
        self.success = True
        self.data = data
        self.error = None


class _FakeClient:
    """Stands in for MadnessAPIClient — records the limit it was asked for."""

    def __init__(self, todos):
        self.todos = todos
        self.requested_limit = None

    async def get_todos(self, limit=None, **kwargs):
        self.requested_limit = limit
        return _FakeResponse({"todos": self.todos[:limit] if limit else self.todos})


@pytest.fixture
def patch_client(monkeypatch):
    def _install(todos):
        client = _FakeClient(todos)

        async def _get_cached_client(**kwargs):
            return client

        monkeypatch.setattr(api_tools, "get_cached_client", _get_cached_client)
        return client

    return _install


def _todo(i, description, notes=""):
    return {"id": f"id-{i}", "description": description, "project": "omnispindle",
            "status": "pending", "priority": "Medium", "created_at": 1780000000,
            "notes": notes, "metadata": {}}


def test_strict_match_wins(patch_client):
    patch_client([
        _todo(0, "fix the auth token refresh"),
        _todo(1, "auth0 device flow docs"),
        _todo(2, "unrelated dashboard tweak"),
    ])
    res = json.loads(asyncio.run(api_tools.search_todos("auth token refresh")))
    assert res["search_mode"] == "strict"
    assert [i["id"] for i in res["items"]] == ["id-0"]


def test_fuzzy_fallback_ranks_by_token_density(patch_client):
    patch_client([
        _todo(0, "dashboard tweak"),
        _todo(1, "auth token rotation"),
        _todo(2, "auth screen"),
    ])
    res = json.loads(asyncio.run(api_tools.search_todos("auth token refresh")))
    assert res["search_mode"] == "fuzzy_or"
    # id-1 hits two tokens, id-2 hits one, id-0 hits none and is dropped
    assert [i["id"] for i in res["items"]] == ["id-1", "id-2"]


def test_fetch_pool_is_larger_than_limit(patch_client):
    """Filtering is client-side — fetching only `limit` would hide older matches."""
    client = patch_client([_todo(i, "auth work") for i in range(50)])
    res = json.loads(asyncio.run(api_tools.search_todos("auth", limit=5)))
    assert client.requested_limit >= 200
    assert len(res["items"]) == 5


def test_multi_hit_fat_notes_auto_briefs(patch_client):
    patch_client([_todo(i, "auth work", notes="x" * 900) for i in range(4)])
    res = json.loads(asyncio.run(api_tools.search_todos("auth")))
    assert res["diet"] == "brief"
    assert all("notes" not in i for i in res["items"])


def test_single_hit_keeps_notes(patch_client):
    patch_client([_todo(0, "auth work", notes="y" * 500), _todo(1, "other thing")])
    res = json.loads(asyncio.run(api_tools.search_todos("auth work")))
    assert res["diet"] == "full"
    assert res["items"][0]["notes"] == "y" * 500


def test_single_hit_oversized_notes_truncated(patch_client):
    patch_client([_todo(0, "auth work", notes="z" * 9000)])
    res = json.loads(asyncio.run(api_tools.search_todos("auth work")))
    assert res["diet"] == "truncated"
    assert "9000 chars total" in res["items"][0]["notes"]


def test_brief_true_forces_strip(patch_client):
    patch_client([_todo(0, "auth work", notes="short")])
    res = json.loads(asyncio.run(api_tools.search_todos("auth work", brief=True)))
    assert res["diet"] == "brief"
    assert "notes" not in res["items"][0]
