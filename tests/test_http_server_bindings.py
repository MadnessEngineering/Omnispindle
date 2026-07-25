"""Guard: http_server.py must not pass auth_ctx positionally into the wrong parameter.

http_server.py forwards every FastMCP tool call to tools.py. When it passes
auth_ctx positionally and tools.py grows a new parameter before ctx, the context
silently lands in that new parameter instead — the tool then runs unauthenticated
against the shared database and the stray Context object corrupts a bool/int arg.
This happened to five tools (query_todos -> since, list_lessons/search_lessons/
list_todos_by_status/list_project_todos -> brief) and to search_todos before that.

Pure AST parsing: no imports, so no DB connection is opened.
"""
import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "Omnispindle"
TOOLS = SRC / "tools.py"
HTTP = SRC / "http_server.py"

_CALL = re.compile(r"return await tools\.(\w+)\((.*)\)\s*$")


def _signatures():
    tree = ast.parse(TOOLS.read_text(), str(TOOLS))
    return {
        node.name: [a.arg for a in node.args.args]
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }


def _split_args(argstr):
    args, depth, cur = [], 0, ""
    for ch in argstr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def _forwarding_calls():
    for lineno, line in enumerate(HTTP.read_text().splitlines(), 1):
        m = _CALL.search(line.strip())
        if m:
            yield lineno, m.group(1), _split_args(m.group(2))


def test_every_forwarded_tool_exists():
    sigs = _signatures()
    missing = [(ln, fn) for ln, fn, _ in _forwarding_calls() if fn not in sigs]
    assert not missing, f"http_server calls tools.py functions that don't exist: {missing}"


def test_auth_ctx_reaches_the_ctx_parameter():
    sigs = _signatures()
    bad = []
    for lineno, fn, args in _forwarding_calls():
        positional = [a for a in args if "=" not in a.split("(")[0]]
        kwargs = [a for a in args if a not in positional]
        if any(a.startswith("ctx=") for a in kwargs):
            continue
        if "auth_ctx" not in positional:
            continue
        idx = positional.index("auth_ctx")
        params = sigs[fn]
        landed = params[idx] if idx < len(params) else "<overflow>"
        if landed != "ctx":
            bad.append(f"http_server.py:{lineno} {fn}() -> auth_ctx lands in '{landed}'")
    assert not bad, "auth_ctx mis-bound (pass ctx=auth_ctx instead):\n" + "\n".join(bad)
