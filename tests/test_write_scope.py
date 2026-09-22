"""
Write-into-scope for create tools (the teams write flip, Phase A).

add_todo / add_lesson route their insert through resolve_scope_collections(write=True):
default (no scope) lands personal — byte-identical; 'team:<slug>' lands the team board
(membership-gated, viewer refused); a denied scope errors BEFORE any insert. The api
path threads scope down api_tools.add_todo -> api_client.create_todo -> POST body.

Fake db_connection / API client; no live Mongo, no HTTP.

Run: python -m pytest tests/test_write_scope.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Idempotency reservation needs a real collection handle; disable the window so the
# create path is a single insert we can assert on. Recall-on-add is off by default.
os.environ["OMNISPINDLE_ADD_TODO_DEDUPE_SECS"] = "0"

import Omnispindle.tools as tools
import Omnispindle.api_tools as api_tools
import Omnispindle.api_client as api_client


class _FakeColl:
    def __init__(self):
        self.inserted = []

    def insert_one(self, doc):
        self.inserted.append(doc)

    def update_one(self, *a, **k):
        pass

    def find_one(self, *a, **k):
        return None


class _FakeConn:
    def __init__(self, deny=None):
        self.calls = []
        self.todos = _FakeColl()
        self.lessons = _FakeColl()
        self.deny = deny

    def resolve_scope_collections(self, user_context, scope=None, write=False):
        self.calls.append((scope, write))
        if self.deny is not None and scope == self.deny:
            raise PermissionError(f"not a member of team '{scope}'")
        return {"todos": self.todos, "lessons": self.lessons, "database": None}


class _Ctx:
    def __init__(self, user):
        self.user = user


USER = {"sub": "auth0|dan", "email": "dan@example.com"}


def _run(coro):
    return asyncio.run(coro)


def _install_write(monkeypatch, conn):
    monkeypatch.setattr(tools, "db_connection", conn)
    # Silence the create path's side effects so the test is hermetic. Close the
    # scheduled coroutine so it isn't left un-awaited (would emit a RuntimeWarning).
    def _noop_spawn(_name, coro=None, _ctx=""):
        if coro is not None and hasattr(coro, "close"):
            coro.close()
    monkeypatch.setattr(tools, "_spawn_background", _noop_spawn)
    monkeypatch.setattr(tools, "enrich_metadata_with_git", lambda md, project=None: md)
    monkeypatch.setattr(tools, "should_validate_project_name", lambda: False)
    monkeypatch.setattr(tools, "invalidate_lesson_tags_cache", lambda *a, **k: None)

    async def _no_embed(_text):
        return None
    monkeypatch.setattr(tools.embeddings, "generate_embedding", _no_embed)


# ---------------------------------------------------------------------------
# add_todo write routing
# ---------------------------------------------------------------------------
def test_add_todo_default_scope_writes_personal(monkeypatch):
    conn = _FakeConn()
    _install_write(monkeypatch, conn)
    out = json.loads(_run(tools.add_todo("do a thing", "omnispindle", ctx=_Ctx(USER))))
    # personal default: resolve called with scope=None, write=True — byte-identical routing
    assert conn.calls == [(None, True)]
    assert len(conn.todos.inserted) == 1
    assert conn.todos.inserted[0]["description"] == "do a thing"
    assert "id" in out


def test_add_todo_team_scope_writes_team(monkeypatch):
    conn = _FakeConn()
    _install_write(monkeypatch, conn)
    _run(tools.add_todo("team task", "omnispindle", scope="team:acme", ctx=_Ctx(USER)))
    assert conn.calls == [("team:acme", True)]
    assert conn.todos.inserted[0]["description"] == "team task"


def test_add_todo_denied_scope_no_insert(monkeypatch):
    conn = _FakeConn(deny="team:secret")
    _install_write(monkeypatch, conn)
    out = json.loads(_run(tools.add_todo("nope", "omnispindle", scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert "not a member" in out["message"]
    assert conn.todos.inserted == []  # gate refused BEFORE any write


# ---------------------------------------------------------------------------
# add_lesson write routing
# ---------------------------------------------------------------------------
def test_add_lesson_team_scope_writes_team(monkeypatch):
    conn = _FakeConn()
    _install_write(monkeypatch, conn)
    out = json.loads(_run(tools.add_lesson("python", "gate", "always fail closed",
                                           tags=["teams"], scope="team:acme", ctx=_Ctx(USER))))
    assert conn.calls == [("team:acme", True)]
    assert conn.lessons.inserted[0]["topic"] == "gate"
    assert "id" in out


def test_add_lesson_denied_scope_no_insert(monkeypatch):
    conn = _FakeConn(deny="team:secret")
    _install_write(monkeypatch, conn)
    out = json.loads(_run(tools.add_lesson("python", "x", "y", scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert conn.lessons.inserted == []


# ---------------------------------------------------------------------------
# api path threads scope down to the POST body
# ---------------------------------------------------------------------------
def test_api_tools_add_todo_forwards_scope(monkeypatch):
    seen = {}

    class _FakeClient:
        async def create_todo(self, description=None, project=None, priority=None, metadata=None, scope=None):
            seen["scope"] = scope
            return type("R", (), {"success": True, "data": {"todo": {"id": "t1"}}, "error": None})()

    async def _fake_get_client(**_kw):
        return _FakeClient()
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    monkeypatch.setattr(api_tools, "_get_auth_from_context", lambda _ctx: (None, None))

    _run(api_tools.add_todo("desc", "proj", scope="team:acme", ctx=None))
    assert seen["scope"] == "team:acme"


def test_api_client_create_todo_puts_scope_in_body(monkeypatch):
    captured = {}

    async def _fake_make_request(self, method, endpoint, **kwargs):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json"] = kwargs.get("json")
        return api_client.APIResponse(success=True, data={"todo": {"id": "t1"}})

    monkeypatch.setattr(api_client.MadnessAPIClient, "_make_request", _fake_make_request)
    client = api_client.MadnessAPIClient()

    _run(client.create_todo("desc", "proj", scope="team:acme"))
    assert captured["json"]["scope"] == "team:acme"

    captured.clear()
    _run(client.create_todo("desc", "proj"))
    assert "scope" not in captured["json"]  # omitted → backend personal default
