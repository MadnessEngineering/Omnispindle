# Lesson Corpus Audit — 2026-06-19

100 lessons, all have 768-dim embeddings (NO_EMBEDDING = 0).

---

## 🗑 CULL CANDIDATES

### Admin Panel BLOAT + DUPLICATE cluster — delete all 3
All three are status-report dumps from one sprint, not lessons. 2374–4706 chars each.
Real knowledge (middleware sequencing) could fit in 300 chars.

| ID | Topic | Chars |
|---|---|---|
| `cbb52b20` | Admin Panel Implementation - Progress Checkpoint | 4706 |
| `035448be` | Admin Panel Testing - Backend Endpoint Verification | 2418 |
| `66640cff` | Admin Panel Integration - Backend Infrastructure | 2374 |

### Human review needed
| ID | Topic | Issue |
|---|---|---|
| `ad45e051` | certbot renewal on Ubuntu with nginx | 2608 chars runbook — trim to 3-bullet distillation or delete |
| `f9932500` | Theme Translation Keys Naming | 3 tags, weakest of theme/i18n cluster — merge into `191ae259` or delete |

---

## ✏️ VAGUE TOPIC (auto-fixed) — slug → human sentence

| ID | Old | New |
|---|---|---|
| `45b277e7` | `omnispindle-todo-tools` | Use complete_todo not update_todo status=completed to finish a task |
| `3a4585d6` | `limit-audit-methodology` | Audit nginx, Express body-parser, and MongoDB limits when migrating to dual-database |
| `35bede25` | `dual-database-debugging` | Add debug logging to trace dual-database routing (personal vs shared MongoDB) |
| `875bed27` | `express-body-parser-limits` | Express JSON body-parser defaults to 100KB — raise limit when adding metadata to endpoints |

---

## 🏷 WEAK TAGS (auto-enriched)

| ID | Topic | Tags added |
|---|---|---|
| `90b5b4d2` | AI Session Management & Context Efficiency | `omnispindle`, `mcp`, `agent-workflow` |
| `3157c2af` | Lab Equipment IoT Specifications Reference | `guardian`, `elemental-machines`, `iot-integration` |
| `495c0679` | Omnispindle create_quest chains arg requires http variant | `create_quest`, `chains`, `http-transport` |
| `cd39b2e4` | Priority Queue Architecture | `inventorium`, `swarmdesk`, `todo-queue` |
| `42b54769` | Button-Based Triage vs Cross-Container Drag | `react`, `inventorium`, `swarmdesk`, `triage` |
| `d1b9776d` | Unreachable Code Detection | `inventorium`, `code-smell` |
| `18e8f378` | API Endpoint Consistency Between Modules | `inventorium`, `api-contract`, `module-coupling` |
| `38de803a` | Syntax Errors Prevent Entire Script Execution | `gotcha`, `node-red` |
| `455d4538` | Global Function Exposure for Dynamic Scripts | `node-red`, `dashboard`, `todomill` |
| `fdf7c926` | Data Structure Normalization in React | `inventorium`, `swarmdesk` |
| `e823ae68` | Enhanced Message Rendering with Types | `inventorium`, `ellie`, `swarmdesk` |

---

## ✅ GOOD (keep as-is, 81 lessons)
All others — clear topics, specific tags, reasonable length, has embeddings.

Notable standouts worth protecting:
- `efe38b7d` — RAG regex fallback tokenization (directly relevant)
- `cd9e0d30` — pre-push deploy race condition
- `d10a10ef` — FastAPI trailing-slash 307
- `791dff7d` — API key bcrypt caching
- `12ec5a48` — Regex entity guards
- `0db0422b` — verify-before-resume workflow

---

## DUPLICATE clusters (human review)
- **Gemini CLI pair** (`94a472b9`, `d3121c93`) — distinct enough, should cross-reference
- **Theme/i18n trio** (`191ae259`, `d158cf36`, `f9932500`) — `f9932500` is weakest, see cull
- **Dual-DB trio** (`3a4585d6`, `35bede25`, `875bed27`) — content distinct, topics auto-fixed above
