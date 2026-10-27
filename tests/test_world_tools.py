"""
World tools: arrange_nodes and show_in_world reach the user's open SwarmDesk.

They push to POST /api/world/push (Inventorium backend). Mock client, no HTTP. What matters:
the payload is exactly what the backend whitelist takes, "nobody heard it" is never reported as
success-without-a-word, and bad input is refused BEFORE a push (each push can spend the user's
model tokens on the other end).

Run: python -m pytest tests/test_world_tools.py
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import Omnispindle.api_tools as api_tools
from Omnispindle.api_client import MadnessAPIClient, APIResponse
from Omnispindle.tool_metadata import TOOL_GROUPS, TOOL_TIERS, TOOL_ACCESS_LEVELS, ToolGroup, ToolTier, ToolAccessLevel
from Omnispindle.tool_loadouts import get_loadout
from Omnispindle.mcp_handler import TOOL_SCHEMAS


class _Resp:
    def __init__(self, data=None, success=True, error=None):
        self.success, self.data, self.error = success, data, error


class _FakeClient:
    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply if reply is not None else _Resp({"success": True, "delivered": 1, "id": 7})

    async def world_push(self, kind, payload):
        self.calls.append((kind, payload))
        return self.reply


def _install(monkeypatch, fake):
    async def _fake_get_client(**_kw):
        return fake
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    monkeypatch.setattr(api_tools, "_require_api_auth", lambda ctx: ("token", None))


def _run(coro):
    return json.loads(asyncio.run(coro))


# ── arrange_nodes ───────────────────────────────────────────────────────────

def test_arrange_pushes_the_request_with_a_presenter(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    out = _run(api_tools.arrange_nodes("  group by what blocks the release  "))
    assert fake.calls == [("arrange-request", {"request": "group by what blocks the release", "presenter": "Claude"})]
    assert out["success"] is True and out["data"]["delivered"] == 1 and out["data"]["event_id"] == 7
    assert "Delivered" in out["message"]


def test_arrange_presenter_is_optional_and_blank_means_none(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    _run(api_tools.arrange_nodes("x", presenter="Codex"))
    _run(api_tools.arrange_nodes("x", presenter="   "))
    _run(api_tools.arrange_nodes("x", presenter=None))
    assert fake.calls[0][1]["presenter"] == "Codex"
    assert "presenter" not in fake.calls[1][1] and "presenter" not in fake.calls[2][1]


def test_arrange_refuses_empty_and_too_long_before_pushing(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    for bad in ["", "   ", None, 7]:
        out = _run(api_tools.arrange_nodes(bad))
        assert out["success"] is False and "request is required" in out["message"]
    out = _run(api_tools.arrange_nodes("x" * 501))
    assert out["success"] is False and "501" in out["message"] and "500" in out["message"]
    assert fake.calls == [], "nothing was pushed for bad input"
    assert _run(api_tools.arrange_nodes("x" * 500))["success"] is True, "exactly 500 is allowed"


def test_nobody_listening_is_said_plainly_and_is_not_a_failure_to_retry_blindly(monkeypatch):
    fake = _FakeClient(_Resp({"success": True, "delivered": 0, "id": None})); _install(monkeypatch, fake)
    out = _run(api_tools.arrange_nodes("group them"))
    assert out["success"] is True and out["data"]["delivered"] == 0
    assert "NOT delivered" in out["message"] and "nothing was queued" in out["message"]
    assert "Linked" in out["message"], "it tells the agent what to ask the user to check"


def test_a_failed_push_reports_the_backend_error(monkeypatch):
    fake = _FakeClient(_Resp(success=False, error="Client error (429): At most 30 pushes per 60s.")); _install(monkeypatch, fake)
    out = _run(api_tools.arrange_nodes("x"))
    assert out["success"] is False and "429" in out["message"]


def test_an_exception_becomes_an_error_not_a_crash(monkeypatch):
    class Boom:
        async def world_push(self, kind, payload):
            raise RuntimeError("socket gone")
    _install(monkeypatch, Boom())
    out = _run(api_tools.arrange_nodes("x"))
    assert out["success"] is False and "socket gone" in out["message"]


# ── show_in_world ───────────────────────────────────────────────────────────

def test_show_pushes_what_it_was_given_and_nothing_else(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    out = _run(api_tools.show_in_world(highlights=["t1", "src/a.js"], links=[{"a": "t1", "b": "t2", "label": "blocks"}],
                                       notes=[{"target": "t1", "text": "start here"}], title=" Blast radius ", focus="t1"))
    kind, payload = fake.calls[0]
    assert kind == "show"
    assert payload == {"highlights": ["t1", "src/a.js"], "links": [{"a": "t1", "b": "t2", "label": "blocks"}],
                       "notes": [{"target": "t1", "text": "start here"}], "title": "Blast radius", "focus": "t1",
                       "presenter": "Claude"}
    assert out["success"] is True and out["data"]["delivered"] == 1


def test_show_concepts_are_pushed_cleaned_and_may_stand_alone(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    out = _run(api_tools.show_in_world(concepts=[{"id": "retry", "label": " Retry budget ", "text": "cap at 3", "near": "t1", "color": "red"},
                                                 {"id": "q:owner", "label": "Who owns it?", "text": ""}],
                                       links=[{"a": "retry", "b": "q:owner", "label": "asks"}], presenter="Codex"))
    assert out["success"] is True
    payload = fake.calls[0][1]
    assert payload["concepts"] == [{"id": "retry", "label": "Retry budget", "text": "cap at 3", "near": "t1"},
                                   {"id": "q:owner", "label": "Who owns it?"}], "known fields only, blanks dropped"
    assert payload["presenter"] == "Codex"
    alone = _run(api_tools.show_in_world(concepts='[{"id": "a", "label": "An idea"}]'))
    assert alone["success"] is True and fake.calls[1][1]["concepts"] == [{"id": "a", "label": "An idea"}]


def test_show_concepts_absent_means_no_key_and_blank_presenter_means_none(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    _run(api_tools.show_in_world(highlights=["t1"], presenter="  "))
    assert "concepts" not in fake.calls[0][1] and "presenter" not in fake.calls[0][1]


def test_show_refuses_concepts_the_page_could_not_name(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    cases = [
        (dict(concepts=[{"id": "a"}]), "concepts[0]"),
        (dict(concepts=["a"]), "concepts[0]"),
        (dict(concepts=[{"label": "no id"}]), "concepts[0].id"),
        (dict(concepts=[{"id": "my idea", "label": "x"}]), "concepts[0].id"),   # the backend would strip the space and orphan its links
        (dict(concepts=[{"id": "x" * 41, "label": "x"}]), "concepts[0].id"),
        (dict(concepts=[{"id": "a", "label": "x"}, {"id": "a", "label": "y"}]), "used twice"),
        (dict(concepts="nope"), "must be a list"),
    ]
    for kwargs, expect in cases:
        out = _run(api_tools.show_in_world(**kwargs))
        assert out["success"] is False and expect in out["message"], (kwargs, out)
    assert fake.calls == [], "nothing was pushed for bad input"


def test_show_title_and_focus_are_omitted_when_absent_or_blank(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    _run(api_tools.show_in_world(highlights=["t1"], title="  ", focus=None))
    assert "title" not in fake.calls[0][1] and "focus" not in fake.calls[0][1]


def test_show_accepts_lists_written_as_json_text(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    out = _run(api_tools.show_in_world(highlights='["t1","t2"]', links='[{"a":"t1","b":"t2"}]', notes=""))
    assert out["success"] is True
    assert fake.calls[0][1]["highlights"] == ["t1", "t2"] and fake.calls[0][1]["links"] == [{"a": "t1", "b": "t2"}]
    assert fake.calls[0][1]["notes"] == []


def test_show_refuses_bad_input_before_pushing(monkeypatch):
    fake = _FakeClient(); _install(monkeypatch, fake)
    cases = [
        (dict(), "at least one"),
        (dict(highlights=[]), "at least one"),
        (dict(highlights="not json"), "must be a list"),
        (dict(highlights={"a": 1}), "must be a list"),
        (dict(highlights=["ok", ""]), "highlights[1]"),
        (dict(highlights=[7]), "highlights[0]"),
        (dict(links=[{"a": "x"}]), "links[0]"),
        (dict(links=["x"]), "links[0]"),
        (dict(notes=[{"target": "x"}]), "notes[0]"),
        (dict(notes=[{"text": "x"}]), "notes[0]"),
    ]
    for kwargs, expect in cases:
        out = _run(api_tools.show_in_world(**kwargs))
        assert out["success"] is False and expect in out["message"], (kwargs, out)
    assert fake.calls == [], "nothing was pushed for bad input"


def test_show_nobody_listening_is_said_plainly(monkeypatch):
    fake = _FakeClient(_Resp({"success": True, "delivered": 0})); _install(monkeypatch, fake)
    out = _run(api_tools.show_in_world(highlights=["t1"]))
    assert out["data"]["delivered"] == 0 and "NOT delivered" in out["message"]


# ── the client method ───────────────────────────────────────────────────────

def test_client_posts_to_the_world_push_route(monkeypatch):
    seen = {}
    async def fake_request(self, method, endpoint, **kw):
        seen.update(method=method, endpoint=endpoint, kw=kw)
        return APIResponse(success=True, data={"delivered": 1})
    monkeypatch.setattr(MadnessAPIClient, "_make_request", fake_request)
    client = MadnessAPIClient(auth_token="t")
    resp = asyncio.run(client.world_push("show", {"highlights": ["t1"]}))
    assert resp.success and seen["method"] == "POST" and seen["endpoint"] == "/world/push"
    assert seen["kw"]["json"] == {"kind": "show", "payload": {"highlights": ["t1"]}}


# ── registration: Pro, full loadouts only, a schema that matches ────────────

def test_world_tools_are_pro_remote_safe_and_in_their_own_group():
    for name in ("arrange_nodes", "show_in_world"):
        assert TOOL_GROUPS[name] == ToolGroup.WORLD
        assert TOOL_TIERS[name] == ToolTier.PRO, "SwarmDesk is a Pro feature, so are the tools that only reach it"
        assert TOOL_ACCESS_LEVELS[name] == ToolAccessLevel.REMOTE_SAFE


def test_only_the_full_loadout_carries_them():
    for name in ("arrange_nodes", "show_in_world"):
        assert name in get_loadout("full", mode="remote"), f"{name} missing from the full loadout"
        for narrow in ("lightweight", "read_only", "write_only", "admin", "agent_preflight", "lessons"):
            assert name not in get_loadout(narrow, mode="remote"), f"{name} leaked into {narrow}"


def test_the_remote_schema_names_the_required_argument():
    assert TOOL_SCHEMAS["arrange_nodes"]["inputSchema"]["required"] == ["request"]
    props = TOOL_SCHEMAS["show_in_world"]["inputSchema"]["properties"]
    assert set(props) == {"highlights", "links", "notes", "concepts", "title", "focus", "presenter"}
    assert "required" not in TOOL_SCHEMAS["show_in_world"]["inputSchema"]


# ── the credential reaches api_tools over the remote route ──────────────────
# Found 2026-10-26 by calling the tools over real MCP JSON-RPC with an API key: "Authentication
# required". The handler built Context(user=<verified user>) and the user never carries the raw key,
# so EVERY api_tools tool (sessions too) failed for a remote API-key connection.

from Omnispindle.context import Context
from Omnispindle.mcp_handler import _credential_from_request


class _Req:
    def __init__(self, headers):
        self.headers = headers


def test_an_api_key_on_the_context_becomes_the_api_key():
    ctx = Context(user={"email": "d@x"}, credential="omni_abc123")
    assert api_tools._get_auth_from_context(ctx) == (None, "omni_abc123")


def test_a_jwt_on_the_context_becomes_the_access_token():
    ctx = Context(user={"email": "d@x"}, credential="aaa.bbb.ccc")
    assert api_tools._get_auth_from_context(ctx) == ("aaa.bbb.ccc", None)


def test_credentials_already_on_the_user_win_and_stdio_is_unchanged():
    assert api_tools._get_auth_from_context(Context(user={"api_key": "omni_user"}, credential="omni_other")) == (None, "omni_user")
    assert api_tools._get_auth_from_context(Context(user={"access_token": "tok"})) == ("tok", None)
    assert api_tools._get_auth_from_context(Context(user={"email": "d@x"})) == (None, None)
    assert api_tools._get_auth_from_context(None) == (None, None)


def test_the_credential_never_shows_in_a_printed_context_or_the_user():
    user = {"email": "d@x", "auth_method": "api_key"}
    ctx = Context(user=user, credential="omni_SECRETSECRET")
    assert "SECRET" not in repr(ctx) and "SECRET" not in str(ctx)
    assert "SECRET" not in json.dumps(ctx.user), "the raw key must not be put on the user dict (it is handed to loggers)"


def test_the_header_parser_takes_only_a_bearer_token():
    assert _credential_from_request(_Req({"authorization": "Bearer omni_abc"})) == "omni_abc"
    assert _credential_from_request(_Req({"authorization": "bearer  aaa.bbb.ccc "})) == "aaa.bbb.ccc"
    for bad in ["", "Bearer", "Bearer   ", "Basic dXNlcjpwYXNz", "omni_abc", None]:
        headers = {} if bad is None else {"authorization": bad}
        assert _credential_from_request(_Req(headers)) is None, bad
    assert _credential_from_request(object()) is None, "a request without headers is not a crash"


def test_an_api_key_forwarded_by_the_backend_proxy_is_read_from_its_own_header():
    # backend/routes/mcp.js strips an omni_ key from Authorization and sends it here instead
    assert _credential_from_request(_Req({"x-forwarded-credential": "omni_abc123"})) == "omni_abc123"
    assert _credential_from_request(_Req({"x-forwarded-credential": "  omni_abc123 "})) == "omni_abc123"
    assert _credential_from_request(_Req({"x-forwarded-credential": "   "})) is None
    assert _credential_from_request(_Req({"authorization": "Bearer aaa.bbb.ccc", "x-forwarded-credential": "omni_other"})) == "aaa.bbb.ccc", \
        "when a bearer is present it wins"
    assert _credential_from_request(_Req({"authorization": "Basic dXNlcjpwYXNz", "x-forwarded-credential": "omni_abc"})) == "omni_abc"


def test_a_world_tool_authenticates_from_the_context_credential(monkeypatch):
    # No monkeypatched _require_api_auth here: the real one, fed only by ctx.credential
    seen = {}
    async def _fake_get_client(**kw):
        seen.update(kw)
        return _FakeClient()
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    out = _run(api_tools.arrange_nodes("group them", ctx=Context(user={"email": "d@x"}, credential="omni_abc123")))
    assert out["success"] is True and seen == {"auth_token": None, "api_key": "omni_abc123", "base_url": None}
    out = _run(api_tools.arrange_nodes("group them", ctx=Context(user={"email": "d@x"})))
    assert out["success"] is False and "Authentication required" in out["message"]


# ── the loopback URL: skip Cloudflare from the same host, for the world tools only ───────────
# From eaws the public API URL answers with Cloudflare's 'Just a moment...' (403). Found 2026-10-26.

from Omnispindle import api_client as api_client_module


def test_loopback_url_is_read_from_the_environment_and_blank_means_none(monkeypatch):
    monkeypatch.delenv("MADNESS_LOOPBACK_API_URL", raising=False)
    assert api_client_module.loopback_api_url() is None
    monkeypatch.setenv("MADNESS_LOOPBACK_API_URL", "  http://localhost:9192/api ")
    assert api_client_module.loopback_api_url() == "http://localhost:9192/api"
    monkeypatch.setenv("MADNESS_LOOPBACK_API_URL", "   ")
    assert api_client_module.loopback_api_url() is None


def test_a_world_tool_asks_for_the_loopback_base_url(monkeypatch):
    monkeypatch.setenv("MADNESS_LOOPBACK_API_URL", "http://localhost:9192/api")
    seen = {}
    async def _fake_get_client(**kw):
        seen.update(kw)
        return _FakeClient()
    monkeypatch.setattr(api_tools, "get_cached_client", _fake_get_client)
    monkeypatch.setattr(api_tools, "_require_api_auth", lambda ctx: (None, "omni_abc"))
    _run(api_tools.show_in_world(highlights=["t1"]))
    assert seen["base_url"] == "http://localhost:9192/api"


def test_the_client_cache_keeps_a_loopback_client_apart_from_the_public_one():
    async def go():
        public = await api_client_module.get_cached_client(api_key="omni_cache_test")
        loop = await api_client_module.get_cached_client(api_key="omni_cache_test", base_url="http://localhost:9192/api")
        again = await api_client_module.get_cached_client(api_key="omni_cache_test", base_url="http://localhost:9192/api")
        try:
            return public, loop, again
        finally:
            await api_client_module.close_all_cached_clients()
    public, loop, again = asyncio.run(go())
    assert public is not loop and loop is again
    assert loop.base_url == "http://localhost:9192/api" and public.base_url != loop.base_url
