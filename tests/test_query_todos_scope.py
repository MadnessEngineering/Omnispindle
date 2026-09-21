"""
query_todos cross-scope fan-out (audit #13, the list-merge slice).

Proves scope='all' merges personal + shared + team todos, tags each row with its
_scope, sorts by created_at desc, and pages the MERGED set — and that an explicit
scope narrows / a denied team scope surfaces the PermissionError. Fake
db_connection; no live Mongo. The real response_shaping (compact/diet) runs.

Run: python -m pytest tests/test_query_todos_scope.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.tools as tools


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction):
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=(direction < 0))
        return self

    def limit(self, n):
        if n:
            self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeTodos:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query=None, _projection=None):
        # Return copies so the tool's _scope tagging can't mutate the fixture.
        return _FakeCursor([dict(d) for d in self._docs])


def _cols(docs):
    return {"todos": _FakeTodos(docs), "database": type("D", (), {"name": "x"})()}


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


def _run(coro):
    return asyncio.run(coro)


class _Ctx:
    def __init__(self, user):
        self.user = user


USER = {"sub": "auth0|dan", "email": "dan@example.com"}


def _install(monkeypatch, conn):
    monkeypatch.setattr(tools, "db_connection", conn)


def test_all_merges_and_tags_scope(monkeypatch):
    pairs = [
        ("personal", _cols([{"id": "p1", "description": "mine", "created_at": 30}])),
        ("shared", _cols([{"id": "s1", "description": "ours", "created_at": 20}])),
        ("team:acme", _cols([{"id": "t1", "description": "team", "created_at": 40}])),
    ]
    _install(monkeypatch, _FakeConn(pairs))

    out = json.loads(_run(tools.query_todos(exclude_completed=False, brief=False, ctx=_Ctx(USER))))
    items = out["items"]
    # merged, sorted by created_at desc across scopes: team(40) > personal(30) > shared(20)
    assert [i["id"] for i in items] == ["t1", "p1", "s1"]
    # each row carries its provenance
    assert {i["id"]: i["_scope"] for i in items} == {"t1": "team:acme", "p1": "personal", "s1": "shared"}
    assert out["source"] == "all"


def test_paging_over_merged_set(monkeypatch):
    pairs = [
        ("personal", _cols([{"id": "p1", "created_at": 50}, {"id": "p2", "created_at": 10}])),
        ("shared", _cols([{"id": "s1", "created_at": 40}, {"id": "s2", "created_at": 20}])),
    ]
    _install(monkeypatch, _FakeConn(pairs))
    # global order desc: p1(50) s1(40) s2(20) p2(10); offset 1 limit 2 → s1, s2
    out = json.loads(_run(tools.query_todos(exclude_completed=False, brief=False, offset=1, limit=2, ctx=_Ctx(USER))))
    assert [i["id"] for i in out["items"]] == ["s1", "s2"]


def test_explicit_personal_scope_narrows(monkeypatch):
    pairs = [
        ("personal", _cols([{"id": "p1", "created_at": 1}])),
        ("shared", _cols([{"id": "s1", "created_at": 2}])),
    ]
    _install(monkeypatch, _FakeConn(pairs))
    out = json.loads(_run(tools.query_todos(exclude_completed=False, brief=False, scope="personal", ctx=_Ctx(USER))))
    assert [i["id"] for i in out["items"]] == ["p1"]
    assert out["source"] == "personal"


def test_denied_team_scope_surfaces_error(monkeypatch):
    _install(monkeypatch, _FakeConn([], raise_for="team:secret"))
    out = json.loads(_run(tools.query_todos(scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert "not a member" in out["message"]
