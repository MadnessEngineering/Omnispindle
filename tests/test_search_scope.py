"""
Cross-scope fan-out for the search / lesson-list tools (audit #13 tail).

Two wire-sides, one contract — a search or lesson list surfaces personal + shared
+ your teams by default, each row _scope-tagged, and narrows on an explicit scope:

  * local search_todos  — routes both passes through query_todos, forwarding scope
  * api   search_todos  — forwards scope='all' to the backend candidate-pool fetch
                          (was personal-only, so fuzzy never saw shared/team todos)
  * list_lessons / grep_lessons / search_lessons — fan out over
                          resolve_scope_collection_list, tag, merge by created_at

Fake db_connection / API client; no live Mongo, no HTTP. Real response_shaping runs.

Run: python -m pytest tests/test_search_scope.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.tools as tools
import Omnispindle.api_tools as api_tools


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction):
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0) or 0, reverse=(direction < 0))
        return self

    def limit(self, n):
        if n:
            self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeLessons:
    """Ignores the query filter (returns all) — fan-out/merge/tag is what's tested;
    the two-pass strict/fuzzy token logic is pre-existing and unchanged."""
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query=None, _projection=None):
        return _FakeCursor([dict(d) for d in self._docs])


def _cols(docs):
    return {"lessons": _FakeLessons(docs), "database": type("D", (), {"name": "x"})()}


class _FakeConn:
    def __init__(self, pairs, raise_for=None):
        self._pairs = pairs
        self._raise_for = raise_for

    def resolve_scope_collection_list(self, user_context, scope=None, write=False):
        if self._raise_for is not None and scope == self._raise_for:
            raise PermissionError(f"not a member of team '{scope}'")
        if scope in (None, "all"):
            return self._pairs
        for label, cols in self._pairs:
            if label == scope:
                return [(label, cols)]
        raise PermissionError(f"not a member of '{scope}'")


class _Ctx:
    def __init__(self, user):
        self.user = user


USER = {"sub": "auth0|dan", "email": "dan@example.com"}


def _run(coro):
    return asyncio.run(coro)


def _lesson(id_, created_at, **extra):
    return {"id": id_, "topic": f"topic {id_}", "lesson_learned": f"body {id_}",
            "language": "python", "created_at": created_at, **extra}


# ---------------------------------------------------------------------------
# list_lessons fan-out
# ---------------------------------------------------------------------------
def test_list_lessons_merges_and_tags_scope(monkeypatch):
    pairs = [
        ("personal", _cols([_lesson("p1", 30)])),
        ("shared", _cols([_lesson("s1", 20)])),
        ("team:acme", _cols([_lesson("t1", 40)])),
    ]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.list_lessons(brief=False, ctx=_Ctx(USER))))
    items = out["items"]
    # global created_at desc across scopes: t1(40) > p1(30) > s1(20)
    assert [i["id"] for i in items] == ["t1", "p1", "s1"]
    assert {i["id"]: i["_scope"] for i in items} == {"t1": "team:acme", "p1": "personal", "s1": "shared"}


def test_list_lessons_brief_keeps_scope_tag(monkeypatch):
    pairs = [("personal", _cols([_lesson("p1", 30)])), ("shared", _cols([_lesson("s1", 20)]))]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.list_lessons(brief=True, ctx=_Ctx(USER))))
    # _scope must survive the brief allowlist (it was added to _BRIEF_LESSON_KEEP)
    assert all("_scope" in i for i in out["items"])
    assert {i["id"]: i["_scope"] for i in out["items"]} == {"p1": "personal", "s1": "shared"}


def test_list_lessons_explicit_scope_narrows(monkeypatch):
    pairs = [("personal", _cols([_lesson("p1", 1)])), ("shared", _cols([_lesson("s1", 2)]))]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.list_lessons(brief=False, scope="shared", ctx=_Ctx(USER))))
    assert [i["id"] for i in out["items"]] == ["s1"]


def test_list_lessons_denied_team_surfaces_error(monkeypatch):
    monkeypatch.setattr(tools, "db_connection", _FakeConn([], raise_for="team:secret"))
    out = json.loads(_run(tools.list_lessons(scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert "not a member" in out["message"]


def test_list_lessons_limit_applies_to_merged_set(monkeypatch):
    pairs = [
        ("personal", _cols([_lesson("p1", 50), _lesson("p2", 10)])),
        ("shared", _cols([_lesson("s1", 40), _lesson("s2", 20)])),
    ]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.list_lessons(brief=False, limit=2, ctx=_Ctx(USER))))
    # global desc p1(50) s1(40) s2(20) p2(10); limit 2 → p1, s1
    assert [i["id"] for i in out["items"]] == ["p1", "s1"]


# ---------------------------------------------------------------------------
# grep_lessons / search_lessons fan-out
# ---------------------------------------------------------------------------
def test_grep_lessons_merges_and_tags(monkeypatch):
    pairs = [
        ("personal", _cols([_lesson("p1", 30)])),
        ("team:acme", _cols([_lesson("t1", 40)])),
    ]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.grep_lessons("body", ctx=_Ctx(USER))))
    assert [i["id"] for i in out["items"]] == ["t1", "p1"]
    assert {i["id"]: i["_scope"] for i in out["items"]} == {"t1": "team:acme", "p1": "personal"}


def test_search_lessons_strict_merges_and_tags(monkeypatch):
    pairs = [
        ("personal", _cols([_lesson("p1", 30)])),
        ("shared", _cols([_lesson("s1", 20)])),
    ]
    monkeypatch.setattr(tools, "db_connection", _FakeConn(pairs))
    out = json.loads(_run(tools.search_lessons("body", brief=False, ctx=_Ctx(USER))))
    assert out["search_mode"] == "strict"
    assert {i["id"]: i["_scope"] for i in out["items"]} == {"p1": "personal", "s1": "shared"}


def test_search_lessons_denied_team_surfaces_error(monkeypatch):
    monkeypatch.setattr(tools, "db_connection", _FakeConn([], raise_for="team:secret"))
    out = json.loads(_run(tools.search_lessons("x", scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert "not a member" in out["message"]


# ---------------------------------------------------------------------------
# local search_todos forwards scope through query_todos (both passes)
# ---------------------------------------------------------------------------
def test_local_search_todos_forwards_scope(monkeypatch):
    seen = []

    async def _fake_query(filter=None, projection=None, limit=100, offset=0,
                          exclude_completed=True, since=None, graph_root=None,
                          brief=None, scope=None, ctx=None):
        seen.append(scope)
        # non-empty so pass 1 short-circuits (no fuzzy pass)
        return json.dumps({"items": [{"id": "x", "description": "hit", "_scope": scope or "all"}],
                           "count": 1, "source": scope or "all"})

    monkeypatch.setattr(tools, "query_todos", _fake_query)
    out = json.loads(_run(tools.search_todos("hit", scope="team:acme", ctx=_Ctx(USER))))
    assert seen == ["team:acme"]
    assert out["items"][0]["_scope"] == "team:acme"


def test_local_search_todos_default_scope_is_none_passthrough(monkeypatch):
    # default scope=None reaches query_todos, which resolves it to 'all' itself
    seen = []

    async def _fake_query(filter=None, scope=None, ctx=None, **kw):
        seen.append(scope)
        return json.dumps({"items": [{"id": "x", "description": "hit"}], "count": 1})

    monkeypatch.setattr(tools, "query_todos", _fake_query)
    _run(tools.search_todos("hit", ctx=_Ctx(USER)))
    assert seen == [None]


# ---------------------------------------------------------------------------
# api search_todos forwards scope to the backend pool fetch
# ---------------------------------------------------------------------------
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
            {"id": "t1", "description": "team hit", "_scope": "team:acme", "created_at": 40},
            {"id": "p1", "description": "personal hit", "_scope": "personal", "created_at": 30},
        ]})


def _install_api(monkeypatch, fake):
    async def _fake_get_client(**_kw):
        return fake
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    monkeypatch.setattr(api_tools, "_get_auth_from_context", lambda _ctx: (None, None))


def test_api_search_todos_defaults_scope_all(monkeypatch):
    fake = _FakeClient()
    _install_api(monkeypatch, fake)
    out = json.loads(_run(api_tools.search_todos("hit", brief=False, ctx=None)))
    assert fake.scope_calls == ["all"]
    # both scopes reachable in the pool → both survive the strict AND on 'hit'
    assert {i["id"]: i.get("_scope") for i in out["items"]} == {"t1": "team:acme", "p1": "personal"}


def test_api_search_todos_explicit_scope_forwarded(monkeypatch):
    fake = _FakeClient()
    _install_api(monkeypatch, fake)
    _run(api_tools.search_todos("hit", scope="shared", ctx=None))
    assert fake.scope_calls == ["shared"]
