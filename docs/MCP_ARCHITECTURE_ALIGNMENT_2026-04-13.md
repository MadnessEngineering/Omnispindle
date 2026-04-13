# MCP Architecture Alignment (April 13, 2026)

## Why this memo exists
Recent changes introduced runtime drift between:
- documented/public MCP contract (`/api/mcp`),
- backend proxy assumptions (Inventorium),
- and actual Omnispindle runtime behavior in production (`/mcp` streamable FastMCP).

This note records the observed state and proposes a stable path.

## Current contract (what clients are told)
- Public docs point users to: `https://madnessinteractive.cc/api/mcp/`
- Example command:
  - `claude mcp add --transport http omnispindle https://madnessinteractive.cc/api/mcp/ --header "Authorization: Bearer ..."`
- Inventorium backend proxies JSON-RPC to `http://localhost:8000/api/mcp`.

## Drift observed in production
- Repo PM2 config says `Omnispindle-HTTP` should run:
  - `python3.11 -m src.Omnispindle.http_server`
- Actual PM2 process was running:
  - `fastmcp run src/Omnispindle/http_server.py --transport http --host 0.0.0.0 --port 8000 --skip-env`
- That process served `/mcp` (streamable transport), not `/api/mcp`.
- Backend logs showed:
  - `POST /api/mcp -> 404` on Omnispindle
  - `ECONNREFUSED 127.0.0.1:8000` during restarts

## Dependency drift observed
- Repo pins `fastmcp==2.2.8` in `requirements.txt` and `pyproject.toml`.
- Production host had `fastmcp 3.2.3` installed in user site-packages.
- FastMCP 3 transport behavior differs and triggered runtime incompatibility:
  - `tools/list` returned `cannot import name 'current_execution' from 'docket.dependencies'`.

## Immediate compatibility bridge added
`src/Omnispindle/http_server.py` now supports both operator workflows:
- Import mode (`fastmcp run ...`) still works (exports `mcp` instance).
- Module mode (`python -m src.Omnispindle.http_server`) now boots legacy FastAPI `/api/mcp` via `run_web_server()`.

This preserves long-standing PM2 commands and Inventorium’s `/api/mcp` contract.

## Recommended stabilization order
1. Restore PM2 to config-defined command for `Omnispindle-HTTP`.
2. Keep `/api/mcp` as canonical public contract.
3. Pin and enforce runtime environment isolation (venv/uv) so host package drift cannot silently change transport behavior.
4. Treat FastMCP streamable `/mcp` as an internal migration track, not production default, until compatibility tests pass.

## Deployment verification checklist
1. `pm2 describe Omnispindle-HTTP` matches ecosystem command.
2. `curl -i -X POST http://127.0.0.1:8000/api/mcp ...` returns non-404 (typically 401 without auth, 200 with valid auth).
3. Backend `POST /api/mcp` no longer logs upstream 404.
4. MCP client initialize/tools list succeeds through `https://madnessinteractive.cc/api/mcp/` with bearer token.

