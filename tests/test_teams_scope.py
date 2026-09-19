"""
Teams scope resolution — the Python MCP membership gate (TEAMS_AUDIT #13).

Pure-logic unit tests, no live Mongo: the security decisions live in
parse_scope_token / match_team_member / is_team_database, and
resolve_scope_collections is exercised against a fake Mongo client so its
fail-closed team gate is covered without a database.

Run: python -m pytest tests/test_teams_scope.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from Omnispindle.database import (
    Database,
    is_team_database,
    parse_scope_token,
    match_team_member,
)


# --------------------------------------------------------------------------- #
# is_team_database
# --------------------------------------------------------------------------- #
def test_is_team_database():
    assert is_team_database("team_acme") is True
    assert is_team_database("team_elemental_machines") is True
    assert is_team_database("user_dan_example_com") is False
    assert is_team_database("swarmonomicon") is False
    assert is_team_database("") is False
    assert is_team_database(None) is False
    assert is_team_database(42) is False


# --------------------------------------------------------------------------- #
# parse_scope_token
# --------------------------------------------------------------------------- #
def test_parse_scope_token_personal_and_shared():
    assert parse_scope_token(None) == ("personal", None)
    assert parse_scope_token("") == ("personal", None)
    assert parse_scope_token("personal") == ("personal", None)
    assert parse_scope_token("shared") == ("shared", None)
    assert parse_scope_token("swarmonomicon") == ("shared", None)


def test_parse_scope_token_team():
    assert parse_scope_token("team:acme") == ("team", "acme")
    assert parse_scope_token("team:elemental_machines") == ("team", "elemental_machines")


def test_parse_scope_token_malformed_team_raises():
    with pytest.raises(ValueError):
        parse_scope_token("team:")


def test_parse_scope_token_junk_falls_back_to_personal():
    # Never guess shared/team from an unrecognised token — fail safe to personal.
    assert parse_scope_token("garbage") == ("personal", None)
    assert parse_scope_token("teamacme") == ("personal", None)  # no colon


# --------------------------------------------------------------------------- #
# match_team_member
# --------------------------------------------------------------------------- #
TEAM = {
    "slug": "acme",
    "db_name": "team_acme",
    "members": [
        {"sub": "google-oauth2|123", "email": "dan@acme.com", "role": "editor"},
        {"sub": "auth0|viewer@acme.com", "email": "viewer@acme.com", "role": "viewer"},
    ],
}


def test_match_by_sub():
    m = match_team_member(TEAM, {"sub": "google-oauth2|123", "email": "x@y.com"})
    assert m and m["role"] == "editor"


def test_match_by_email():
    m = match_team_member(TEAM, {"sub": "some-other-sub", "email": "dan@acme.com"})
    assert m and m["role"] == "editor"


def test_match_by_auth0_email_alias():
    # A member row keyed on 'auth0|<email>' matches a caller carrying that email.
    m = match_team_member(TEAM, {"email": "viewer@acme.com"})
    assert m and m["role"] == "viewer"


def test_non_member_returns_none():
    assert match_team_member(TEAM, {"sub": "nobody", "email": "ghost@nowhere.com"}) is None


def test_unverified_email_denied():
    # email_verified explicitly False → never matched, even if the row would match.
    assert match_team_member(TEAM, {"sub": "google-oauth2|123", "email_verified": False}) is None


def test_absent_email_verified_is_allowed():
    # Absent flag = trusted server path; not re-litigated.
    m = match_team_member(TEAM, {"sub": "google-oauth2|123"})
    assert m and m["role"] == "editor"


def test_empty_inputs():
    assert match_team_member(None, {"sub": "x"}) is None
    assert match_team_member(TEAM, None) is None
    assert match_team_member({"members": []}, {"sub": "x"}) is None


# --------------------------------------------------------------------------- #
# resolve_scope_collections — fake Mongo client, real gate
# --------------------------------------------------------------------------- #
class _FakeTeams:
    def __init__(self, doc):
        self._doc = doc

    def find_one(self, _query):
        return self._doc


class _FakeDb:
    def __init__(self, name, team_doc=None):
        self.name = name
        self._team_doc = team_doc

    def __getitem__(self, coll):
        if coll == "teams":
            return _FakeTeams(self._team_doc)
        return f"{self.name}::{coll}"


class _FakeClient:
    def __init__(self, team_doc=None):
        self._team_doc = team_doc

    def __getitem__(self, dbname):
        return _FakeDb(dbname, self._team_doc)


def make_db(team_doc=TEAM):
    """A Database instance with fakes wired in — bypasses __new__ (no real Mongo)."""
    d = object.__new__(Database)
    d.client = _FakeClient(team_doc)
    d.shared_db = _FakeDb("swarmonomicon", team_doc)
    d._user_databases = {}
    return d


EDITOR = {"sub": "google-oauth2|123", "email": "dan@acme.com"}
VIEWER = {"sub": "auth0|viewer@acme.com", "email": "viewer@acme.com"}
OUTSIDER = {"sub": "nobody", "email": "ghost@nowhere.com"}


def test_resolve_personal_scope():
    cols = make_db().resolve_scope_collections(EDITOR, "personal")
    assert cols["todos"] == "user_dan_acme_com::todos"


def test_resolve_shared_scope():
    cols = make_db().resolve_scope_collections(EDITOR, "shared")
    assert cols["todos"] == "swarmonomicon::todos"


def test_resolve_team_member_read():
    cols = make_db().resolve_scope_collections(EDITOR, "team:acme", write=False)
    assert cols["todos"] == "team_acme::todos"
    assert cols["database"].name == "team_acme"


def test_resolve_team_member_write():
    cols = make_db().resolve_scope_collections(EDITOR, "team:acme", write=True)
    assert cols["todos"] == "team_acme::todos"


def test_resolve_team_non_member_denied():
    with pytest.raises(PermissionError):
        make_db().resolve_scope_collections(OUTSIDER, "team:acme")


def test_resolve_team_viewer_read_ok_write_denied():
    # viewer may read
    cols = make_db().resolve_scope_collections(VIEWER, "team:acme", write=False)
    assert cols["todos"] == "team_acme::todos"
    # but not write
    with pytest.raises(PermissionError):
        make_db().resolve_scope_collections(VIEWER, "team:acme", write=True)


def test_resolve_team_unknown_slug_denied():
    with pytest.raises(PermissionError):
        make_db(team_doc=None).resolve_scope_collections(EDITOR, "team:ghost")


def test_resolve_team_invalid_db_name_denied():
    bad = {"slug": "acme", "db_name": "user_not_a_team", "members": [{"sub": "google-oauth2|123", "role": "editor"}]}
    with pytest.raises(PermissionError):
        make_db(team_doc=bad).resolve_scope_collections(EDITOR, "team:acme")


def test_resolve_malformed_team_token_raises_value_error():
    with pytest.raises(ValueError):
        make_db().resolve_scope_collections(EDITOR, "team:")
