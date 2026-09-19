"""
_find_todo_across_scopes — the single by-ID probe shared by get/update/complete/
delete_todo. Proves the personal→shared fallback and, by extension, the delete
asymmetry fix (delete previously probed the user DB only and 404'd shared todos —
audit #13). Pure logic against a fake db_connection; no live Mongo.

Run: python -m pytest tests/test_todo_fallback.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.tools as tools


class _FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)

    def find_one(self, query):
        for d in self.docs:
            if d.get("id") == query.get("id"):
                return d
        return None


class _FakeDbHandle:
    def __init__(self, name):
        self.name = name


class _FakeConn:
    """Stands in for db_connection: personal handle for a user_context, shared for None."""
    def __init__(self, user_docs=None, shared_docs=None):
        self._user_docs = user_docs or []
        self._shared_docs = shared_docs or []

    def get_collections(self, user_context):
        if user_context:
            return {
                "todos": _FakeCollection(self._user_docs),
                "deleted_todos": _FakeCollection([]),
                "database": _FakeDbHandle("user_dan_example_com"),
            }
        return {
            "todos": _FakeCollection(self._shared_docs),
            "deleted_todos": _FakeCollection([]),
            "database": _FakeDbHandle("swarmonomicon"),
        }


USER = {"sub": "auth0|dan", "email": "dan@example.com"}


def _with_conn(monkeypatch, **kwargs):
    monkeypatch.setattr(tools, "db_connection", _FakeConn(**kwargs))


def test_found_in_personal(monkeypatch):
    _with_conn(monkeypatch, user_docs=[{"id": "t1", "description": "mine"}])
    todo, collections, source, searched = tools._find_todo_across_scopes("t1", USER)
    assert todo["description"] == "mine"
    assert source == "user"
    assert collections["database"].name == "user_dan_example_com"
    assert searched == ["user database 'user_dan_example_com'"]


def test_falls_back_to_shared(monkeypatch):
    # Not in personal, present in shared — the case delete_todo used to 404.
    _with_conn(monkeypatch, user_docs=[], shared_docs=[{"id": "t2", "description": "team-ish"}])
    todo, collections, source, searched = tools._find_todo_across_scopes("t2", USER)
    assert todo["description"] == "team-ish"
    assert source == "shared"
    assert collections["database"].name == "swarmonomicon"
    assert searched == [
        "user database 'user_dan_example_com'",
        "shared database 'swarmonomicon'",
    ]


def test_no_sub_skips_personal_probe(monkeypatch):
    # Unauthenticated / no Auth0 sub → personal scope is not consulted at all.
    _with_conn(monkeypatch, user_docs=[{"id": "t3"}], shared_docs=[{"id": "t3", "loc": "shared"}])
    todo, collections, source, searched = tools._find_todo_across_scopes("t3", {"email": "x@y.com"})
    assert source == "shared"
    assert todo["loc"] == "shared"
    assert searched == ["shared database 'swarmonomicon'"]


def test_not_found_anywhere(monkeypatch):
    _with_conn(monkeypatch, user_docs=[], shared_docs=[])
    todo, collections, source, searched = tools._find_todo_across_scopes("ghost", USER)
    assert todo is None
    assert collections is None
    assert source is None
    assert searched == [
        "user database 'user_dan_example_com'",
        "shared database 'swarmonomicon'",
    ]


def test_personal_wins_over_shared_on_id_collision(monkeypatch):
    # First match wins, personal first — a personal copy shadows a shared duplicate.
    _with_conn(
        monkeypatch,
        user_docs=[{"id": "dup", "loc": "personal"}],
        shared_docs=[{"id": "dup", "loc": "shared"}],
    )
    todo, _collections, source, _searched = tools._find_todo_across_scopes("dup", USER)
    assert source == "user"
    assert todo["loc"] == "personal"
