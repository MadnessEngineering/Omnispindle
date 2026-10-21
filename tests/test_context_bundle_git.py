"""Git-aware work_context for get_context_bundle."""
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from Omnispindle import tools


def _match(doc, q):
    for k, cond in q.items():
        v = doc.get(k)
        if isinstance(cond, dict):
            if "$in" in cond and v not in cond["$in"]:
                return False
            if "$regex" in cond:
                import re
                if not re.search(cond["$regex"], str(v or ""), re.I):
                    return False
            if "$ne" in cond and v == cond["$ne"]:
                return False
        elif v != cond:
            return False
    return True


class FakeCursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return FakeCursor(self[:n])


class FakeColl:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q=None, proj=None):
        q = q or {}
        if "$or" in q:
            return FakeCursor()
        return FakeCursor(d for d in self.docs if _match(d, q))

    def find_one(self, q=None):
        return None


def todo(id, status="pending", files=None, branch=None, project="proj", desc="d"):
    meta = {}
    if files is not None:
        meta["files"] = files
    if branch:
        meta["branch"] = branch
    return {"id": id, "description": desc, "status": status, "priority": "High", "project": project, "metadata": meta}


TODOS = [
    todo("a", files=["src/app-store.ts", "src/app.tsx"]),
    todo("b", status="in_progress", files=["other.py"]),
    todo("c", status="review", files=["src/app-store.ts"]),
    todo("d", files=["./app.tsx"], branch="feat/x"),
    todo("e", status="blocked"),
    todo("f", files=["src/app-store.ts"], project="elsewhere"),
    todo("g", status="in_progress", files=["z.py"], branch="feat/x", desc="x" * 200),
]


async def run(**kw):
    colls = {"todos": FakeColl(TODOS), "lessons": FakeColl([])}
    with patch.object(tools.db_connection, "get_collections", return_value=colls), \
         patch.object(tools, "inventorium_sessions_list", return_value=json.dumps({"success": True, "data": {"sessions": []}})):
        return json.loads(await tools.get_context_bundle(**kw))


def test_same_file_rule():
    assert tools._same_file("../../src/app.tsx", "app.tsx")
    assert tools._same_file("./a/b.py", "a/b.py")
    assert tools._same_file("x/y/app.tsx", "y/app.tsx")
    assert not tools._same_file("xapp.tsx", "app.tsx")
    assert not tools._same_file("a.py", "b.py")


def test_string_files_are_split_not_iterated():
    # Some todos store metadata.files as one string; iterating it would match single characters.
    assert tools._as_file_list("src/a.ts, src/b.ts\nc.py") == ["src/a.ts", "src/b.ts", "c.py"]
    assert tools._as_file_list(None) == [] and tools._as_file_list({"x": 1}) == []
    items = [{"id": "s", "status": "pending", "metadata": {"files": "src/app.tsx, lib/x.py"}}]
    top, with_files, matched = tools._rank_work_todos(items, ["x/src/app.tsx", "a"], None, 3)
    assert [t["id"] for t in top] == ["s"] and top[0]["score"] == 3
    top, _, matched = tools._rank_work_todos(items, ["p", "y"], None, 3)
    assert matched == 0


@pytest.mark.asyncio
async def test_ranking_scores_and_why():
    r = await run(project="proj", files=["src/app-store.ts", "app.tsx"], branch="feat/x", limit=10)
    wc = r["bundle"]["work_context"]
    byid = {t["id"]: t for t in wc["todos"]}
    assert byid["a"]["score"] == 6
    assert byid["a"]["why"] == ["touches app-store.ts, app.tsx"]
    assert byid["d"]["score"] == 4 and byid["d"]["why"] == ["touches app.tsx", "same branch"]
    assert byid["g"]["score"] == 3 and byid["g"]["why"] == ["in progress", "same branch"]
    assert len(byid["g"]["description"]) == 120
    assert [t["id"] for t in wc["todos"]] == ["a", "d", "g", "b"]
    scores = [t["score"] for t in wc["todos"]]
    assert scores == sorted(scores, reverse=True)
    assert byid["b"]["score"] == 2 and "e" not in byid  # e: blocked, no files, score 0
    assert wc["counts"] == {"scanned": 5, "with_files": 4, "matched": 4}


@pytest.mark.asyncio
async def test_in_progress_alone_scores_and_limit():
    r = await run(project="proj", files=["nothing.py"], limit=1)
    wc = r["bundle"]["work_context"]
    assert [t["id"] for t in wc["todos"]] == ["b"]
    assert len(wc["todos"]) == 1


@pytest.mark.asyncio
async def test_review_excluded_and_project_scoped():
    r = await run(project="proj", files=["src/app-store.ts"], limit=10)
    ids = {t["id"] for t in r["bundle"]["work_context"]["todos"]}
    assert "c" not in ids and "f" not in ids


@pytest.mark.asyncio
async def test_project_todos_omitted_with_work_context():
    r = await run(project="proj", files=["src/app-store.ts"])
    assert "work_context" in r["bundle"]
    assert "project_todos" not in r["bundle"]
    assert "blocked_todos" in r["bundle"]
    r = await run(project="proj", branch="feat/x")
    assert "project_todos" not in r["bundle"] and "work_context" in r["bundle"]


@pytest.mark.asyncio
async def test_regex_lessons_note():
    lessons = FakeColl([])
    colls = {"todos": FakeColl(TODOS), "lessons": lessons}
    with patch.object(tools.db_connection, "get_collections", return_value=colls), \
         patch.object(tools.embeddings, "is_available", return_value=False), \
         patch.object(tools, "inventorium_sessions_list", return_value=json.dumps({"success": True, "data": {"sessions": []}})):
        r = json.loads(await tools.get_context_bundle(project="proj", files=["a.py"], query="deploy hooks"))
    wc = r["bundle"]["work_context"]
    assert wc["method"] == "regex" and "keyword" in wc["note"] and wc["lessons"] == []


@pytest.mark.asyncio
async def test_unchanged_without_new_params():
    r = await run(project="proj")
    assert "work_context" not in r["bundle"]
    assert [t["id"] for t in r["bundle"]["project_todos"]["items"]] == ["a", "d"]
    assert r["summary"]["query"] == "project=proj"
    assert "work_context" not in r["summary"]["sections_returned"]
