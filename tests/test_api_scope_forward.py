"""
Hybrid/API path forwards scope and preserves the backend's _scope tag.

In hybrid mode query_todos proxies api_tools → api_client → Node REST. This pins
that (a) the scope arg reaches api_client.get_todos, and (b) the _scope tag the
backend attaches survives the API→MCP conversion. Mock client, no HTTP.

Run: python -m pytest tests/test_api_scope_forward.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.api_tools as api_tools


class _FakeResp:
    def __init__(self, data):
        self.success = True
        self.data = data
        self.error = None


class _FakeClient:
    def __init__(self):
        self.scope_calls = []

    async def get_todos(self, project=None, status=None, priority=None, limit=100, scope=None):
        self.scope_calls.append(scope)
        return _FakeResp({"todos": [
            {"id": "t1", "description": "team work", "_scope": "team:acme", "created_at": 40},
            {"id": "p1", "description": "mine", "_scope": "personal", "created_at": 30},
        ]})


def _install(monkeypatch, fake):
    async def _fake_get_client(**_kw):
        return fake
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    monkeypatch.setattr(api_tools, "_get_auth_from_context", lambda _ctx: (None, None))


def test_scope_forwarded_to_get_todos(monkeypatch):
    fake = _FakeClient()
    _install(monkeypatch, fake)
    asyncio.run(api_tools.query_todos(scope="all", brief=False, ctx=None))
    assert fake.scope_calls == ["all"]


def test_scope_tag_survives_api_to_mcp_conversion(monkeypatch):
    fake = _FakeClient()
    _install(monkeypatch, fake)
    out = json.loads(asyncio.run(api_tools.query_todos(scope="all", brief=False, ctx=None)))
    by_id = {i["id"]: i.get("_scope") for i in out["items"]}
    assert by_id == {"t1": "team:acme", "p1": "personal"}


def test_list_wrappers_forward_scope(monkeypatch):
    fake = _FakeClient()
    _install(monkeypatch, fake)
    asyncio.run(api_tools.list_todos_by_status("pending", scope="team:acme", ctx=None))
    asyncio.run(api_tools.list_project_todos("inventorium", scope="shared", ctx=None))
    assert fake.scope_calls == ["team:acme", "shared"]
