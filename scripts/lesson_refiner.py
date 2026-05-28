#!/usr/bin/env python3
"""
Lesson Refiner — local web GUI for curating the lessons corpus.

A throwaway-but-handy single-file tool for reviewing, editing, de-duplicating,
and re-embedding lessons_learned documents across all user databases.

Built to support the preflight_rag/find_relevant refining effort: the semantic
search panel surfaces real cosine similarity scores so you can eyeball whether
embeddings are actually working, and the duplicate finder flags near-identical
lessons that pollute RAG results.

Reuses src.Omnispindle.embeddings so embedding behavior matches production.

Usage:
    python scripts/lesson_refiner.py [--host 0.0.0.0] [--port 8675]

On eaws, run under pm2:
    pm2 start scripts/lesson_refiner.py --name lesson-refiner --interpreter python3 -- --port 8675

Requires GEMINI_API_KEY in env for any embedding operation (re-embed, semantic
search, duplicate detection). Editing/listing works without it.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient
from dotenv import load_dotenv

from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

load_dotenv()

from src.Omnispindle.embeddings import (
    generate_embedding,
    embedding_text_for_lesson,
    cosine_similarity,
    is_available,
    EMBEDDING_DIMS,
)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
SHARED_DB = os.getenv("MONGODB_DB", "swarmonomicon")
LESSONS = "lessons_learned"

client = MongoClient(MONGODB_URI)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def target_databases():
    """All databases that may hold lessons: user_* plus the shared DB."""
    names = client.list_database_names()
    targets = [n for n in names if n.startswith("user_") or n == SHARED_DB]
    return sorted(set(targets))


def lessons_col(db_name):
    return client[db_name][LESSONS]


def serialize(doc):
    """Strip the heavy embedding vector; expose only whether it exists + dims."""
    emb = doc.get("embedding")
    return {
        "id": doc.get("id"),
        "topic": doc.get("topic", ""),
        "language": doc.get("language", ""),
        "lesson_learned": doc.get("lesson_learned", ""),
        "tags": doc.get("tags", []) or [],
        "created_at": doc.get("created_at"),
        "has_embedding": bool(emb) and len(emb) == EMBEDDING_DIMS,
        "embedding_dims": len(emb) if emb else 0,
    }


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

async def api_dbs(request):
    out = []
    for name in target_databases():
        col = lessons_col(name)
        total = col.count_documents({})
        if total == 0:
            continue
        with_emb = col.count_documents(
            {"embedding": {"$exists": True}, "$expr": {"$eq": [{"$size": "$embedding"}, EMBEDDING_DIMS]}}
        )
        out.append({"db": name, "total": total, "embedded": with_emb, "missing": total - with_emb})
    return JSONResponse({"databases": out, "embeddings_available": is_available()})


async def api_lessons(request):
    db = request.query_params.get("db")
    if not db:
        return JSONResponse({"error": "db param required"}, status_code=400)
    docs = list(lessons_col(db).find().sort("created_at", -1))
    return JSONResponse({"lessons": [serialize(d) for d in docs]})


async def api_save(request):
    db = request.query_params.get("db")
    lesson_id = request.path_params["lesson_id"]
    body = await request.json()
    updates = {}
    for field in ("topic", "language", "lesson_learned"):
        if field in body:
            updates[field] = body[field]
    if "tags" in body:
        tags = body["tags"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        updates["tags"] = tags
    if not updates:
        return JSONResponse({"error": "no updatable fields"}, status_code=400)

    col = lessons_col(db)
    res = col.update_one({"id": lesson_id}, {"$set": updates})
    if res.matched_count == 0:
        return JSONResponse({"error": "lesson not found"}, status_code=404)

    # Re-embed whenever embeddable content changed (or tags) and key is present
    reembedded = False
    if is_available() and any(k in updates for k in ("topic", "lesson_learned", "language", "tags")):
        doc = col.find_one({"id": lesson_id})
        embedding = await generate_embedding(embedding_text_for_lesson(doc))
        if embedding:
            col.update_one({"id": lesson_id}, {"$set": {"embedding": embedding}})
            reembedded = True

    doc = col.find_one({"id": lesson_id})
    return JSONResponse({"ok": True, "reembedded": reembedded, "lesson": serialize(doc)})


async def api_reembed(request):
    if not is_available():
        return JSONResponse({"error": "GEMINI_API_KEY not set"}, status_code=400)
    db = request.query_params.get("db")
    lesson_id = request.path_params["lesson_id"]
    col = lessons_col(db)
    doc = col.find_one({"id": lesson_id})
    if not doc:
        return JSONResponse({"error": "lesson not found"}, status_code=404)
    embedding = await generate_embedding(embedding_text_for_lesson(doc))
    if not embedding:
        return JSONResponse({"error": "embedding generation failed"}, status_code=502)
    col.update_one({"id": lesson_id}, {"$set": {"embedding": embedding}})
    return JSONResponse({"ok": True, "lesson": serialize(col.find_one({"id": lesson_id}))})


async def api_reembed_missing(request):
    if not is_available():
        return JSONResponse({"error": "GEMINI_API_KEY not set"}, status_code=400)
    db = request.query_params.get("db")
    col = lessons_col(db)
    docs = list(col.find({"embedding": {"$exists": False}}))
    # also catch wrong-dim embeddings
    for d in col.find({"embedding": {"$exists": True}}):
        if not d.get("embedding") or len(d["embedding"]) != EMBEDDING_DIMS:
            docs.append(d)
    embedded, errors = 0, 0
    for doc in docs:
        text = embedding_text_for_lesson(doc)
        if not text.strip():
            continue
        embedding = await generate_embedding(text)
        if embedding:
            col.update_one({"id": doc["id"]}, {"$set": {"embedding": embedding}})
            embedded += 1
        else:
            errors += 1
    return JSONResponse({"ok": True, "embedded": embedded, "errors": errors, "candidates": len(docs)})


async def api_delete(request):
    db = request.query_params.get("db")
    lesson_id = request.path_params["lesson_id"]
    res = lessons_col(db).delete_one({"id": lesson_id})
    if res.deleted_count == 0:
        return JSONResponse({"error": "lesson not found"}, status_code=404)
    return JSONResponse({"ok": True})


async def api_search(request):
    db = request.query_params.get("db")
    body = await request.json()
    query = (body.get("query") or "").strip()
    mode = body.get("mode", "regex")
    limit = int(body.get("limit", 15))
    if not query:
        return JSONResponse({"error": "query required"}, status_code=400)
    col = lessons_col(db)

    if mode == "semantic":
        if not is_available():
            return JSONResponse({"error": "GEMINI_API_KEY not set"}, status_code=400)
        qemb = await generate_embedding(query)
        if not qemb:
            return JSONResponse({"error": "query embedding failed"}, status_code=502)
        scored = []
        for d in col.find({"embedding": {"$exists": True}}):
            emb = d.get("embedding")
            if not emb or len(emb) != EMBEDDING_DIMS:
                continue
            scored.append((cosine_similarity(qemb, emb), d))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, d in scored[:limit]:
            s = serialize(d)
            s["score"] = round(score, 4)
            results.append(s)
        return JSONResponse({"mode": "semantic", "results": results})

    # regex mode
    rx = {"$regex": query, "$options": "i"}
    cursor = col.find({"$or": [{"topic": rx}, {"lesson_learned": rx}, {"tags": rx}]}).limit(limit)
    return JSONResponse({"mode": "regex", "results": [serialize(d) for d in cursor]})


async def api_duplicates(request):
    if not is_available():
        return JSONResponse({"error": "GEMINI_API_KEY not set (duplicate detection needs embeddings)"}, status_code=400)
    db = request.query_params.get("db")
    body = await request.json()
    threshold = float(body.get("threshold", 0.9))
    col = lessons_col(db)
    docs = [d for d in col.find({"embedding": {"$exists": True}}) if d.get("embedding") and len(d["embedding"]) == EMBEDDING_DIMS]
    pairs = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            score = cosine_similarity(docs[i]["embedding"], docs[j]["embedding"])
            if score >= threshold:
                pairs.append({
                    "score": round(score, 4),
                    "a": serialize(docs[i]),
                    "b": serialize(docs[j]),
                })
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return JSONResponse({"pairs": pairs, "scanned": len(docs), "threshold": threshold})


async def index(request):
    return HTMLResponse(PAGE)


# ---------------------------------------------------------------------------
# Frontend (single inline page, vanilla JS, mad-lab dark theme)
# ---------------------------------------------------------------------------

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lesson Refiner</title>
<style>
  :root { --bg:#0a0e12; --panel:#121821; --border:#1e2a38; --cyan:#00ff88; --orange:#ff6b35; --magenta:#ff00ff; --txt:#cfe; --dim:#7a8a9a; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; background:var(--bg); color:var(--txt); }
  header { padding:12px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { font-size:16px; margin:0; color:var(--cyan); letter-spacing:1px; }
  .badge { font-size:11px; padding:2px 8px; border-radius:10px; border:1px solid var(--border); color:var(--dim); }
  .badge.on { color:var(--cyan); border-color:var(--cyan); }
  .badge.off { color:var(--orange); border-color:var(--orange); }
  select, input, textarea, button { font:inherit; background:var(--panel); color:var(--txt); border:1px solid var(--border); border-radius:6px; padding:6px 10px; }
  button { cursor:pointer; }
  button:hover { border-color:var(--cyan); }
  button.danger:hover { border-color:var(--orange); color:var(--orange); }
  .layout { display:grid; grid-template-columns: 320px 1fr; gap:0; height:calc(100vh - 56px); }
  .sidebar { border-right:1px solid var(--border); padding:14px; overflow:auto; }
  .main { padding:14px 18px; overflow:auto; }
  .dbrow { padding:8px 10px; border:1px solid var(--border); border-radius:6px; margin-bottom:6px; cursor:pointer; }
  .dbrow:hover { border-color:var(--cyan); }
  .dbrow.active { border-color:var(--cyan); background:#0f1620; }
  .dbrow .nm { color:var(--cyan); word-break:break-all; }
  .dbrow .stats { font-size:11px; color:var(--dim); margin-top:3px; }
  .miss { color:var(--orange); }
  .section { margin-bottom:20px; }
  .section h2 { font-size:12px; color:var(--orange); text-transform:uppercase; letter-spacing:1px; margin:0 0 8px; }
  .toolbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
  .card { border:1px solid var(--border); border-radius:8px; padding:10px 12px; margin-bottom:10px; background:var(--panel); }
  .card.dirty { border-color:var(--magenta); }
  .card .top { display:flex; justify-content:space-between; gap:8px; align-items:flex-start; }
  .card .meta { font-size:11px; color:var(--dim); }
  .card .id { font-size:10px; color:var(--dim); word-break:break-all; }
  .card textarea { width:100%; min-height:60px; resize:vertical; margin-top:6px; }
  .card .line { display:flex; gap:8px; margin-top:6px; }
  .card .line input { flex:1; }
  .pill { font-size:10px; padding:1px 7px; border-radius:9px; border:1px solid var(--border); }
  .pill.emb { color:var(--cyan); border-color:var(--cyan); }
  .pill.noemb { color:var(--orange); border-color:var(--orange); }
  .pill.score { color:var(--magenta); border-color:var(--magenta); }
  .actions { display:flex; gap:6px; margin-top:8px; }
  .dup { display:grid; grid-template-columns:1fr 1fr; gap:10px; border:1px solid var(--magenta); border-radius:8px; padding:10px; margin-bottom:12px; }
  .dup .hd { grid-column:1/3; color:var(--magenta); font-size:12px; }
  .small { font-size:11px; color:var(--dim); }
  .grow { flex:1; }
  #toast { position:fixed; bottom:16px; right:16px; background:var(--panel); border:1px solid var(--cyan); color:var(--cyan); padding:10px 14px; border-radius:6px; opacity:0; transition:opacity .2s; pointer-events:none; }
  #toast.show { opacity:1; }
  .tabs { display:flex; gap:6px; margin-bottom:12px; }
  .tab { padding:6px 12px; border:1px solid var(--border); border-radius:6px; cursor:pointer; color:var(--dim); }
  .tab.active { color:var(--cyan); border-color:var(--cyan); }
  .hidden { display:none; }
</style>
</head>
<body>
<header>
  <h1>&#129514; LESSON REFINER</h1>
  <span id="embBadge" class="badge">embeddings: ?</span>
  <span class="grow"></span>
  <span class="small">Omnispindle lessons_learned curation</span>
</header>
<div class="layout">
  <div class="sidebar">
    <div class="section">
      <h2>Databases</h2>
      <div id="dbList"></div>
    </div>
  </div>
  <div class="main">
    <div class="tabs">
      <div class="tab active" data-tab="browse">Browse / Edit</div>
      <div class="tab" data-tab="search">Search &amp; Score</div>
      <div class="tab" data-tab="dupes">Duplicates</div>
    </div>

    <div id="tab-browse">
      <div class="toolbar">
        <span id="dbTitle" class="small">Select a database</span>
        <span class="grow"></span>
        <button id="reembedMissing" class="danger">Re-embed missing</button>
        <button id="reload">Reload</button>
      </div>
      <div id="lessonList"></div>
    </div>

    <div id="tab-search" class="hidden">
      <div class="toolbar">
        <input id="q" class="grow" placeholder="3-5 distinctive technical nouns...">
        <select id="mode">
          <option value="semantic">semantic (cosine)</option>
          <option value="regex">regex</option>
        </select>
        <button id="runSearch">Search</button>
      </div>
      <div class="small" style="margin-bottom:8px">Semantic shows real similarity scores — use it to verify embeddings actually work vs regex fallback.</div>
      <div id="searchResults"></div>
    </div>

    <div id="tab-dupes" class="hidden">
      <div class="toolbar">
        <label class="small">threshold</label>
        <input id="thresh" type="number" step="0.01" min="0.5" max="1" value="0.92" style="width:90px">
        <button id="runDupes">Find duplicates</button>
        <span id="dupeInfo" class="small"></span>
      </div>
      <div id="dupeResults"></div>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
let CURRENT_DB = null;
let EMB_AVAILABLE = false;

function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'var(--cyan)' : 'var(--orange)';
  t.style.color = ok ? 'var(--cyan)' : 'var(--orange)';
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2200);
}
async function jget(u){ const r=await fetch(u); return r.json(); }
async function jpost(u,b){ const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}); return r.json(); }
function esc(s){ return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

async function loadDbs(){
  const d = await jget('/api/dbs');
  EMB_AVAILABLE = d.embeddings_available;
  const b = document.getElementById('embBadge');
  b.textContent = 'embeddings: ' + (EMB_AVAILABLE?'ON':'OFF (no GEMINI_API_KEY)');
  b.className = 'badge ' + (EMB_AVAILABLE?'on':'off');
  const el = document.getElementById('dbList');
  el.innerHTML = '';
  d.databases.forEach(db=>{
    const div = document.createElement('div');
    div.className='dbrow'+(db.db===CURRENT_DB?' active':'');
    const missTxt = db.missing>0 ? `<span class="miss">${db.missing} missing</span>` : 'all embedded';
    div.innerHTML = `<div class="nm">${esc(db.db)}</div><div class="stats">${db.total} lessons &middot; ${missTxt}</div>`;
    div.onclick = ()=>{ CURRENT_DB=db.db; loadDbs(); loadLessons(); };
    el.appendChild(div);
  });
}

function lessonCard(l){
  const pill = l.has_embedding ? '<span class="pill emb">embedded</span>' : '<span class="pill noemb">no embedding</span>';
  const score = (l.score!==undefined) ? `<span class="pill score">${l.score}</span>` : '';
  const div = document.createElement('div');
  div.className='card';
  div.dataset.id=l.id;
  div.innerHTML = `
    <div class="top">
      <div class="grow">
        <div class="line"><input class="f-topic" value="${esc(l.topic)}" placeholder="topic"></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end">${score}${pill}</div>
    </div>
    <textarea class="f-lesson" placeholder="lesson_learned">${esc(l.lesson_learned)}</textarea>
    <div class="line">
      <input class="f-lang" value="${esc(l.language)}" placeholder="language" style="max-width:160px">
      <input class="f-tags" value="${esc((l.tags||[]).join(', '))}" placeholder="tags, comma, separated">
    </div>
    <div class="id">${esc(l.id)}</div>
    <div class="actions">
      <button class="save">Save${EMB_AVAILABLE?' + re-embed':''}</button>
      <button class="reembed">Re-embed</button>
      <span class="grow"></span>
      <button class="del danger">Delete</button>
    </div>`;
  const markDirty=()=>div.classList.add('dirty');
  div.querySelectorAll('input,textarea').forEach(i=>i.addEventListener('input',markDirty));
  div.querySelector('.save').onclick=async()=>{
    const body={ topic:div.querySelector('.f-topic').value, lesson_learned:div.querySelector('.f-lesson').value, language:div.querySelector('.f-lang').value, tags:div.querySelector('.f-tags').value };
    const r=await jpost(`/api/lessons/${encodeURIComponent(l.id)}/save?db=${encodeURIComponent(CURRENT_DB)}`,body);
    if(r.ok){ toast('saved'+(r.reembedded?' + re-embedded':'')); div.classList.remove('dirty'); loadDbs(); } else toast(r.error||'save failed',false);
  };
  div.querySelector('.reembed').onclick=async()=>{
    const r=await jpost(`/api/lessons/${encodeURIComponent(l.id)}/reembed?db=${encodeURIComponent(CURRENT_DB)}`);
    if(r.ok){ toast('re-embedded'); loadDbs(); loadLessons(); } else toast(r.error||'failed',false);
  };
  div.querySelector('.del').onclick=async()=>{
    if(!confirm('Delete this lesson permanently?')) return;
    const r=await jpost(`/api/lessons/${encodeURIComponent(l.id)}/delete?db=${encodeURIComponent(CURRENT_DB)}`);
    if(r.ok){ toast('deleted'); div.remove(); loadDbs(); } else toast(r.error||'failed',false);
  };
  return div;
}

async function loadLessons(){
  if(!CURRENT_DB) return;
  document.getElementById('dbTitle').textContent = CURRENT_DB;
  const el=document.getElementById('lessonList'); el.innerHTML='<div class="small">loading…</div>';
  const d=await jget(`/api/lessons?db=${encodeURIComponent(CURRENT_DB)}`);
  el.innerHTML='';
  if(!d.lessons.length){ el.innerHTML='<div class="small">no lessons</div>'; return; }
  d.lessons.forEach(l=>el.appendChild(lessonCard(l)));
}

document.getElementById('reload').onclick=loadLessons;
document.getElementById('reembedMissing').onclick=async()=>{
  if(!CURRENT_DB) return toast('pick a db',false);
  if(!confirm('Re-embed all lessons missing embeddings in '+CURRENT_DB+'?')) return;
  toast('embedding…');
  const r=await jpost(`/api/reembed-missing?db=${encodeURIComponent(CURRENT_DB)}`);
  if(r.ok){ toast(`embedded ${r.embedded}/${r.candidates}, ${r.errors} errors`); loadDbs(); loadLessons(); } else toast(r.error||'failed',false);
};

document.getElementById('runSearch').onclick=async()=>{
  if(!CURRENT_DB) return toast('pick a db',false);
  const q=document.getElementById('q').value, mode=document.getElementById('mode').value;
  const el=document.getElementById('searchResults'); el.innerHTML='<div class="small">searching…</div>';
  const d=await jpost(`/api/search?db=${encodeURIComponent(CURRENT_DB)}`,{query:q,mode});
  el.innerHTML='';
  if(d.error){ toast(d.error,false); el.innerHTML=`<div class="small">${esc(d.error)}</div>`; return; }
  if(!d.results.length){ el.innerHTML='<div class="small">no matches</div>'; return; }
  d.results.forEach(l=>el.appendChild(lessonCard(l)));
};
document.getElementById('q').addEventListener('keydown',e=>{ if(e.key==='Enter') document.getElementById('runSearch').click(); });

document.getElementById('runDupes').onclick=async()=>{
  if(!CURRENT_DB) return toast('pick a db',false);
  const threshold=parseFloat(document.getElementById('thresh').value);
  const el=document.getElementById('dupeResults'); el.innerHTML='<div class="small">scanning…</div>';
  const d=await jpost(`/api/duplicates?db=${encodeURIComponent(CURRENT_DB)}`,{threshold});
  if(d.error){ el.innerHTML=`<div class="small">${esc(d.error)}</div>`; return; }
  document.getElementById('dupeInfo').textContent=`${d.pairs.length} pairs ≥ ${d.threshold} (scanned ${d.scanned})`;
  el.innerHTML='';
  d.pairs.forEach(p=>{
    const div=document.createElement('div'); div.className='dup';
    div.innerHTML=`<div class="hd">similarity ${p.score}</div>`;
    [p.a,p.b].forEach(side=>{
      const c=document.createElement('div'); c.style.fontSize='12px';
      c.innerHTML=`<b>${esc(side.topic)}</b><div class="small">${esc(side.language)} · ${esc((side.tags||[]).join(', '))}</div><div style="margin-top:4px">${esc(side.lesson_learned)}</div><div class="id">${esc(side.id)}</div>`;
      div.appendChild(c);
    });
    el.appendChild(div);
  });
  if(!d.pairs.length) el.innerHTML='<div class="small">no pairs above threshold</div>';
};

document.querySelectorAll('.tab').forEach(t=>{
  t.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    ['browse','search','dupes'].forEach(name=>{
      document.getElementById('tab-'+name).classList.toggle('hidden', name!==t.dataset.tab);
    });
  };
});

loadDbs();
</script>
</body>
</html>"""


routes = [
    Route("/", index),
    Route("/api/dbs", api_dbs),
    Route("/api/lessons", api_lessons),
    Route("/api/lessons/{lesson_id}/save", api_save, methods=["POST"]),
    Route("/api/lessons/{lesson_id}/reembed", api_reembed, methods=["POST"]),
    Route("/api/lessons/{lesson_id}/delete", api_delete, methods=["POST"]),
    Route("/api/reembed-missing", api_reembed_missing, methods=["POST"]),
    Route("/api/search", api_search, methods=["POST"]),
    Route("/api/duplicates", api_duplicates, methods=["POST"]),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Lesson Refiner local web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8675)
    args = parser.parse_args()

    print(f"=== Lesson Refiner ===")
    print(f"MongoDB: {MONGODB_URI}")
    print(f"Embeddings: {'ON' if is_available() else 'OFF (no GEMINI_API_KEY)'}")
    print(f"Serving on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
