"""
By-id ops (get/update/complete/delete) route to an explicit scope (write flip, Phase B).

A bare UUID never crosses into a team (isolation) — you reach a team todo by passing
scope='team:<slug>'. With scope: resolve_scope_collections gates membership (writes
enforce viewer-can't-write) and the op runs in that scope. Without scope: the
personal → shared probe, unchanged. A denied scope errors before any mutation.

Fake db_connection; no live Mongo. Run: python -m pytest tests/test_byid_scope.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.tools as tools


class _FakeColl:
    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]
        self.updated, self.deleted, self.inserted = [], [], []

    def find_one(self, q, *a, **k):
        return next((dict(d) for d in self.docs if d.get('id') == q.get('id')), None)

    def update_one(self, q, upd, *a, **k):
        self.updated.append((q, upd))
        return type('R', (), {'modified_count': 1})()

    def delete_one(self, q, *a, **k):
        self.deleted.append(q)

    def insert_one(self, d, *a, **k):
        self.inserted.append(d)


def _collections(name, todos_docs):
    return {'todos': _FakeColl(todos_docs), 'deleted_todos': _FakeColl(),
            'database': type('D', (), {'name': name})()}


class _FakeConn:
    def __init__(self, personal=None, shared=None, teamdocs=None, deny=None):
        self.calls = []
        self.personal = _collections('user_test', personal or [])
        self.shared = _collections('swarmonomicon', shared or [])
        self.team = _collections('team_acme', teamdocs or [])
        self.deny = deny

    def resolve_scope_collections(self, user_context, scope=None, write=False):
        self.calls.append((scope, write))
        if self.deny is not None and scope == self.deny:
            raise PermissionError(f"not a member of team '{scope}'")
        if scope in ('shared', 'swarmonomicon'):
            return self.shared
        if scope and scope.startswith('team:'):
            return self.team
        return self.personal

    def get_collections(self, user_context):
        return self.personal if user_context else self.shared


class _Ctx:
    def __init__(self, user):
        self.user = user


USER = {"sub": "auth0|dan", "email": "dan@example.com"}
TEAM_TODO = {"id": "t1", "description": "team task", "project": "lab", "status": "pending", "created_at": 100}
PERS_TODO = {"id": "p1", "description": "mine", "project": "lab", "status": "pending", "created_at": 100}


def _run(coro):
    return asyncio.run(coro)


def _install(monkeypatch, conn):
    monkeypatch.setattr(tools, "db_connection", conn)
    def _noop_spawn(_name, coro=None, _ctx=""):
        if coro is not None and hasattr(coro, "close"):
            coro.close()
    monkeypatch.setattr(tools, "_spawn_background", _noop_spawn)
    monkeypatch.setattr(tools, "_is_read_only_user", lambda ctx: False)
    monkeypatch.setattr(tools, "enrich_metadata_with_git", lambda *a, **k: {})
    monkeypatch.setattr(tools, "get_changed_files", lambda *a, **k: [])

    async def _anoop(*a, **k):
        return None
    monkeypatch.setattr(tools, "log_todo_complete", _anoop)
    monkeypatch.setattr(tools, "log_todo_delete", _anoop)
    monkeypatch.setattr(tools.embeddings, "generate_embedding", _anoop)


# --- get_todo ---------------------------------------------------------------
def test_get_todo_team_scope_reads_team(monkeypatch):
    conn = _FakeConn(teamdocs=[TEAM_TODO])
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.get_todo("t1", scope="team:acme", ctx=_Ctx(USER))))
    assert conn.calls == [("team:acme", False)]  # read → write=False
    assert out["id"] == "t1"
    assert out["source"] == "team:acme"


def test_get_todo_no_scope_uses_personal_probe(monkeypatch):
    conn = _FakeConn(personal=[PERS_TODO])
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.get_todo("p1", ctx=_Ctx(USER))))
    assert conn.calls == []  # no scope → _find_todo_across_scopes, not resolve_scope_collections
    assert out["id"] == "p1"


def test_get_todo_denied_team_errors(monkeypatch):
    conn = _FakeConn(deny="team:secret")
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.get_todo("t1", scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert "not a member" in out["message"]


# --- update_todo ------------------------------------------------------------
def test_update_todo_team_scope_writes_team(monkeypatch):
    conn = _FakeConn(teamdocs=[TEAM_TODO])
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.update_todo("t1", {"priority": "High"}, scope="team:acme", ctx=_Ctx(USER))))
    assert conn.calls == [("team:acme", True)]  # write → write=True
    assert out["id"] == "t1"
    assert len(conn.team["todos"].updated) == 1
    assert conn.personal["todos"].updated == []


def test_update_todo_denied_team_no_write(monkeypatch):
    conn = _FakeConn(deny="team:secret")
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.update_todo("t1", {"priority": "High"}, scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert conn.team["todos"].updated == []


# --- complete_todo ----------------------------------------------------------
def test_complete_todo_team_scope_writes_team(monkeypatch):
    conn = _FakeConn(teamdocs=[TEAM_TODO])
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.complete_todo("t1", comment="done", scope="team:acme", ctx=_Ctx(USER))))
    assert conn.calls == [("team:acme", True)]
    assert out["id"] == "t1"
    assert len(conn.team["todos"].updated) == 1


# --- delete_todo ------------------------------------------------------------
def test_delete_todo_team_scope_tombstones_in_team(monkeypatch):
    conn = _FakeConn(teamdocs=[TEAM_TODO])
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.delete_todo("t1", scope="team:acme", ctx=_Ctx(USER))))
    assert conn.calls == [("team:acme", True)]
    assert out["id"] == "t1"
    assert len(conn.team["deleted_todos"].inserted) == 1  # tombstone in team
    assert len(conn.team["todos"].deleted) == 1
    assert conn.personal["deleted_todos"].inserted == []


def test_delete_todo_denied_team_no_delete(monkeypatch):
    conn = _FakeConn(deny="team:secret")
    _install(monkeypatch, conn)
    out = json.loads(_run(tools.delete_todo("t1", scope="team:secret", ctx=_Ctx(USER))))
    assert out["success"] is False
    assert conn.team["todos"].deleted == []
