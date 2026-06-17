# Omnispindle Roadmap — 2026-06-16

## Status Snapshot
- **25 pending** todos, **75 completed**
- Recent wins: deploy race fix, HTTP trailing-slash fix, tool-call hang fix, RAG fixes 1-3, quest system, token Phase 3

---

## Pending Todos by Theme

### 🔥 TOKEN / PERFORMANCE (3)
| ID (short) | Description | Priority |
|---|---|---|
| `38add646` | list_project_todos blows token budget — brief=true/projection drops embedding+coordinates | High |
| `5041a676` | Reduce MCP token consumption — Prong A (caller discipline) + Prong B (uniform brief modes) | Medium |
| `dfc80f0c` | brief mode for find_relevant + preflight_rag (deferred from Phase 3) | Low |

### 🧠 RAG / KNOWLEDGE (2)
| ID (short) | Description | Priority |
|---|---|---|
| `728b8194` | Pitfall classification gate — only mark pitfall if tags contain gotcha\|bug\|error\|broken etc | Medium |
| `dc5188ca` | Audit lessons for mad tinker alignment — improve tags, cull low-value, enrich high-value | Medium |

### 🗺 SPATIAL / METADATA — SwarmDesk (4)
| ID (short) | Description | Priority |
|---|---|---|
| `5461651a` | Add district, effort, coordinates fields to TodoMetadata schema | High |
| `e3322584` | Add query_todos_near spatial proximity tool | High |
| `c65f2abb` | Auto-populate metadata.files from git changed files on complete_todo | Medium |
| `94fd9ba8` | Update add_todo MCP description to encourage semantic coordinate assignment | Medium |

### 🔗 SESSION CONTINUITY / GRAPH (2)
| ID (short) | Description | Priority |
|---|---|---|
| `d66a214d` | Wire Inventorium session context into MCP tools for cross-session continuity | High |
| `a0b2ab0f` | Add todo-to-todo dependency linking via MCP tools | High |

### 🤖 NPC BRAIN (2)
| ID (short) | Description | Priority |
|---|---|---|
| `dc2766d3` | Implement npc_think MCP tool — server-side NPC brain | Medium |
| `ea2c7618` | Implement get_npc_thoughts MCP tool — poll NPC brain results | Medium |

### 💎 GEMINI INTEGRATION (2)
| ID (short) | Description | Priority |
|---|---|---|
| `cd24160c` | To-do launch script: pull into Gemini first for submarine plan before Claude | Medium |
| `01d68736` | Auto-fill empty todo forms with Gemini call (queued background, non-blocking) | Medium |

### 🔍 SEARCH (1)
| ID (short) | Description | Priority |
|---|---|---|
| `1a3a5f87` | Improve todo search fuzzy/partial matching and synonyms | Medium |

### ⚙️ INFRA / CONFIG (3)
| ID (short) | Description | Priority |
|---|---|---|
| `c13e87f6` | Normalize project names — case sensitivity bug | Medium |
| `c9b89e1f` | Re-evaluate tool gating strategy for different agent/client setups | Medium |
| `1b540c23` | Set up Omnispindle MCP connector in claude.ai/settings/connectors | Low |

### 🎮 SWARMDESK UI (1)
| ID (short) | Description | Priority |
|---|---|---|
| `4098892f` | SwarmDesk tag selection should also select tag in gather-tag menu in todo panel | Medium |

### 📣 CONTENT / MARKETING (2)
| ID (short) | Description | Priority |
|---|---|---|
| `b847c044` | Create pocket summary template for Omnispindle | High |
| `b2e08da4` | Plan "The Brain" video — Omnispindle MCP deep dive (7-9 min) | Medium |

### 📚 DOCS / CONFLUENCE (1)
| ID (short) | Description | Priority |
|---|---|---|
| `0ef47346` | Search Confluence DIE space for pages similar to claude-notes on 2026-06-11 DB issue | Medium |

### 🗃 OLDER / LEGACY (2)
| ID (short) | Description | Priority |
|---|---|---|
| `356b7b98` | Demo Script Alignment — update suggested questions + demo responses | Medium |
| `3ca5eedd` | AI Configuration Panel — manage model/prompt settings with testing attributes | Medium |

---

## Proposed Roadmap

### Sprint 1 — Core Stability (affects every session)
**Goal: every MCP call is lean and correct**

1. **`38add646`** — Fix list_project_todos token bloat (brief=true drops embeddings, proven bug)
2. **`5041a676`** — Token reduction Prong A+B (caller discipline + uniform brief modes)
3. **`dfc80f0c`** — brief mode for find_relevant/preflight_rag (deferred Phase 3 item)
4. **`c13e87f6`** — Normalize project names case-sensitivity (cheap bug, cleans data)
5. **`728b8194`** — Pitfall classification gate (stops mislabeling half the results as pitfalls)

### Sprint 2 — Graph / Spatial (powers SwarmDesk 3D)
**Goal: todos have coordinates + can link to each other**

1. **`5461651a`** — Add district/effort/coordinates to TodoMetadata schema
2. **`94fd9ba8`** — Update add_todo description to encourage semantic coordinate assignment
3. **`e3322584`** — Add query_todos_near spatial proximity tool
4. **`a0b2ab0f`** — Todo-to-todo dependency linking via MCP tools
5. **`c65f2abb`** — Auto-populate metadata.files from git on complete_todo

### Sprint 3 — Session Continuity + Intelligence
**Goal: agents remember what happened last session + work smarter**

1. **`d66a214d`** — Wire Inventorium session context into MCP tools
2. **`1a3a5f87`** — Fuzzy/partial todo search (agents find todos they're looking for)
3. **`dc5188ca`** — Audit and align lessons corpus for better RAG recall
4. **`cd24160c`** — Gemini pre-processing for to-do launch script (saves tokens)

### Sprint 4 — NPC Brain + AI Layer
**Goal: NPCs can think, Gemini fills gaps**

1. **`dc2766d3`** — npc_think MCP tool (server-side NPC brain)
2. **`ea2c7618`** — get_npc_thoughts MCP tool (poll brain results)
3. **`01d68736`** — Auto-fill todo forms with Gemini (background, non-blocking)

### Sprint 5 — Polish + Backlog
**Goal: clean up the long tail**

1. **`b847c044`** — Pocket summary template
2. **`c9b89e1f`** — Re-evaluate tool gating strategy
3. **`4098892f`** — SwarmDesk tag selection sync
4. **`1b540c23`** — claude.ai connector setup (Low — unblocks scheduled agents)
5. **`b2e08da4`** — Plan "The Brain" video
6. **`356b7b98`** — Demo script alignment
7. **`3ca5eedd`** — AI Configuration Panel
8. **`0ef47346`** — Confluence research

---

## Candidates to Cancel / Defer Indefinitely

None yet — all 25 pending todos have a clear purpose. Review older items (`356b7b98`, `3ca5eedd`) at Sprint 5 — they may be superseded by current architecture.

---

## Quick Wins (can do in < 1 hour each)
- `c13e87f6` — project name normalization (one-liner validator)
- `94fd9ba8` — add_todo docstring update
- `728b8194` — pitfall gate keyword check (small conditional)
- `b847c044` — pocket summary template (pure docs/prompt work)
