# Project Workspace — Design Doc (v2, corrected)

> Status: Design (v2) · Date: Aug 14, 2026
> Scope: Source registry + notebook cells + journey state. Cross-source joins (DuckDB) deferred to Phase 2.
> **v2 changes:** corrected competitive baseline (Hex/ChatGPT/Julius verified), workspace-level shared connections (kills the one-off vs systemic paradox), context-binder model (not an assembly bucket), governance first-class.

---

## 1. The model (one paragraph)

**A project is the container for one problem/journey. Data is the material — but the material is *referenced*, never re-collected.**

Today analysis is scoped to a *dataset* (the dropdown model): switch dataset → lose the journey (questions, findings, corrections), can't relate datasets, and the AI's memory (beliefs/corrections) forgets when you switch.

The project inverts this — and, critically, the **connections are centralized at the workspace (team) level and shared across all projects**, exactly like Hex's workspace-level data connections. The analyst never builds a connection for a single question; the connections already exist, the project just references them.

```
Workspace (team/tenant) — owns the CONNECTIONS (Postgres, Slack, Snowflake…)
  └─ Project = one problem / one analysis journey
       ├─ Problem statement (first cell, editable)
       ├─ Bound sources (references to workspace connections + context materials)
       ├─ Cells (question → answer → finding, with provenance)
       └─ Journey state (what's answered, what's the next pivotal question)
```

Uploading a dataset **auto-creates a project** (zero extra setup — identical friction to today). The user *grows* the project by binding related sources and asking questions. Memory (beliefs, corrections, metric definitions) scopes to the project, so the AI learns across *all* the data for that problem.

---

## 2. Naming decision (verified collision in codebase)

**"Workspace" is already taken** — it's the *tenant/team* entity:

- `version2/backend/api/workspace/routes.py` — team CRUD + membership (owner/admin/member/viewer)
- `version2/backend/db/tenant_guard.py` — every doc in `TENANT_SCOPED_COLLECTIONS` is pinned to `workspace_id`
- `version2/frontend/src/store/workspaceStore.js` — current team context (id, role)

So the analysis container is named **`project`** (not "notebook" — avoids the Jupyter code-cell association; the product is zero-code and problem-first). Mapping:

| Concept | Codebase name | Existing? |
|---|---|---|
| Team / tenant boundary | `workspace` | ✅ exists (`workspaces` collection) |
| **Shared data connections** (owned by workspace) | `connections` | ✅ exists (`databases` + `dlt` connectors) |
| Analysis container (one problem) | `project` | 🆕 new |
| Dataset (material inside project) | `upload` / `dataset` | ✅ exists |

The project doc carries `workspace_id` (tenant scoping) **and** `owner_id`, and joins the `TENANT_SCOPED_COLLECTIONS` set in `tenant_guard.py` — so multi-tenancy works exactly like every other tenant-scoped entity, with zero new isolation machinery.

---

## 3. Competitive reality (corrected — verified, not assumed)

**v2 correction: the April/earlier framing overstated competitor weaknesses. Verified as of Aug 2026:**

| Competitor | Verified capability | Verified weakness (where the moat actually is) |
|---|---|---|
| **Hex** | Native connections to Snowflake, BigQuery, Redshift, Databricks, Postgres, MySQL, SQL Server, DuckDB, Athena; **workspace-level connections shared across projects**; SQL + Python notebooks | Code-first (requires analysts); no correction-learning loop; no governed metric store exposed to non-technical users |
| **ChatGPT** | Memory (preference-level), Advanced Data Analysis (Python), Google Drive/OneDrive connections, 2026 Projects feature | **Loses uploaded data + transformations — users must re-upload** (verified complaints). Memory is conversational/preference, not durable queryable analysis state |
| **Julius** | Postgres, MySQL, Snowflake, BigQuery, SQL Server, OneDrive, SharePoint connectors | **No scheduled refreshes, no multi-user collaboration on the same dataset** (verified) |

**The real moat is narrow but real:** durable, *queryable* analysis state (definitions, corrections, past answers that survive and refresh) — vs. ChatGPT's conversational memory that drops the data, and Julius's single-user no-refresh model. Hex is the genuine competitor on architecture; the differentiation is the correction loop + governed metrics + zero-code problem-first flow.

---

## 4. Architecture: the context binder (not an assembly bucket)

**The ruthless-review correction:** a "container for mess" is a junk drawer. The project must *do* something with the sources — and must never require re-collecting them. Two structural rules:

### Rule 1 — Connections are workspace-level and shared (kills the one-off paradox)

- The workspace (team) owns the connections: `databases` (Postgres/MySQL/MongoDB), `dlt` sources (Slack, Salesforce, HubSpot…), Sheets.
- A project **references** a connection — it never re-authenticates, never re-ingests from scratch.
- One-off question? The connection already exists; the analyst just queries it. No "build the pipeline" step per question.
- This is Hex's model, confirmed: *"Workspace data connections can be used across multiple projects and are shared with all workspace members by default."*

### Rule 2 — Two kinds of bound material: data sources + context sources

Not everything bound to a project becomes a queryable table. The project is a **context binder** that layers messy human context on top of structured data that already lives in the connected systems:

| Kind | Examples | Role |
|---|---|---|
| **Data sources** | DB tables, Slack exports, Sheets, uploaded files | parquet → analyzed (existing substrate) |
| **Context sources** | CEO's churn-definition PDF, business rules, metric definitions, past reports | memory / beliefs / RAG → *informs the AI's answers* |

The AI **does the assembly**: it parses the churn-definition PDF, translates it into SQL `WHERE` clauses, and joins against the connected warehouse data — autonomously. The analyst states the problem; the AI binds context to data.

---

## 5. Ingestion contract (from the ETL handbook)

Every source bound to a project must go through the **existing** production-grade extraction machinery — never a bespoke fetch. The rules, mapped to what already exists:

| Contract | Rule | Already exists (verified) |
|---|---|---|
| **Incremental** | Check watermark → fetch only the delta | `services/dlt/state.py` (high-water marks → MongoDB), `services/databases/connectors/*.py` → `extract_incremental(increment_column)` |
| **Idempotent** | Rerun twice → same result; row-dedup on | `services/pipeline/process.py` (compare-and-swap guard); `services/pipeline/clean.py` (dedup — **flip default ON for project materialization**) |
| **Graceful** | One failing source degrades, never blocks the project | per-connector try/except in dlt runner + DB connectors |
| **Converged** | Every source → parquet → dataset → profile → semantic layer | uploads / dlt / databases / Sheets all already converge |

The project's **freshness UI is the incremental contract made visible**: each source card shows `last_sync`, `watermark`, `status` — "synced yesterday, watermark at X", or "sync failed 3d ago, using last good snapshot". That's ETL health as a product feature.

---

## 6. Data model (new MongoDB collections)

All new collections are tenant-scoped (added to `TENANT_SCOPED_COLLECTIONS`).

### `projects`
```json
{
  "_id": "...",
  "workspace_id": "<tenant>",
  "owner_id": "<user>",
  "name": "Churn dropped in Q3 — why?",
  "problem_statement": "…",           // first cell content
  "bound_source_ids": ["…", "…"],     // references, not copies
  "status": "draft | active | archived",
  "created_at": "...", "updated_at": "..."
}
```

### `project_sources` (the binder — references workspace connections + context materials)
```json
{
  "_id": "...",
  "project_id": "...",
  "workspace_id": "<tenant>",
  "kind": "data | context",
  "ref": {
    "connection_type": "database | dlt | google_sheets | file | document",
    "conn_id": "…",                    // references EXISTING workspace connection
    "table": "…" | "source_type": "slack" | "dataset_id": "…" | "document_id": "…"
  },
  "sync": {
    "status": "idle | syncing | ok | error",
    "last_sync_at": "...",
    "watermark": "…",
    "next_sync": "scheduled | on_demand",
    "error": "…"
  },
  "created_at": "..."
}
```

### `project_cells`
```json
{
  "_id": "...",
  "project_id": "...",
  "workspace_id": "<tenant>",
  "kind": "problem | question | answer | note | chart | table",
  "order": 1,
  "question": "…",
  "answer_md": "…",
  "provenance": {
    "sql": "…",
    "metric_definition_id": "…",
    "row_count": 1234,
    "date_range": ["2026-01-01", "2026-07-31"],
    "dataset_ids": ["…"]
  },
  "status": "pending | answered | blocked",
  "created_at": "...", "updated_at": "..."
}
```

---

## 7. API surface

New router `api/projects/routes.py` (mounted as `/api/projects`, tenant-scoped):

| Endpoint | Purpose |
|---|---|
| `POST /api/projects` | Create (auto-created on first upload if none exists) |
| `GET /api/projects` | List user's projects (replaces "dataset dropdown" as the launcher) |
| `GET /api/projects/{id}` | Project detail: bound sources + cells + journey state |
| `PUT /api/projects/{id}` | Update name / problem statement |
| `DELETE /api/projects/{id}` | Archive/delete |
| `POST /api/projects/{id}/sources` | **Bind** a source (references existing workspace connection — never re-creates) |
| `GET /api/projects/{id}/sources` | Source list with sync state (freshness UI) |
| `POST /api/projects/{id}/sources/{sid}/sync` | Trigger sync via **existing** dlt/DB extractors (incremental, idempotent) |
| `POST /api/projects/{id}/cells` | Add a cell (question → run through chat/QUIS pipeline) |
| `GET /api/projects/{id}/cells` | Ordered cell list |
| `PUT /api/projects/{id}/cells/{cid}` | Update (incl. corrections → belief store) |
| `POST /api/projects/{id}/journey/next-question` | **Journey state:** return the next pivotal question grounded in findings + problem statement |

---

## 8. Journey-state loop (the "hard questions throughout the journey")

```
Problem statement (cell 0)
      │
      ▼
[1] Decompose  — MECE-decompose the problem into its critical sub-questions
                 (resurrect ThinkerAgent.mece_analysis — currently 100% dead code)
      │
      ▼
[2] Answer     — each question runs through the existing chat/QUIS pipeline
                 (correction capture + belief store already wired there)
      │
      ▼
[3] Reflect    — what did the answer imply? (QUIS critic + insight reflection)
      │
      ▼
[4] Derive     — surface the NEXT hard question, grounded in what was just found
                 ("The West dropped — is it one product or across the board?")
                 Replaces today's generic follow-up chips (prompts/sql.py get_follow_up_prompt)
      │
      ▼
      └────── repeat until the problem is answered ──────┘
```

Key principle: **the strongest questions are *derived* from evidence, not pre-generated.** The decompose step (1) gives the initial skeleton; the derive step (4) is what makes each next question feel like a senior analyst asking it.

`journey/next-question` is a **pure backend endpoint** — fully testable without the frontend. Phase A ships this endpoint + the cell model; the UI panel (Phase C) is a thin consumer.

---

## 9. Governance & security (first-class, not an afterthought)

The ruthless-review warning: ingesting raw PII + financials + customer complaints into an AI context is a compliance honeypot. Enterprise IT blocks this instantly. Mitigations (most already exist):

1. **The connection, not the AI, stays the data owner.** The tool queries connected systems; it does not become a copy-all store.
2. **PII detection/redaction** — already built (`services/privacy`, data quality agent).
3. **Privacy settings: column-name + sample-row sharing controls** — already built.
4. **Context sources are opt-in and visible** — the analyst chooses what the AI may read; nothing silently joins.
5. **Tenant isolation is enforced at the DB layer** (`tenant_guard.py`) — projects, sources, and cells join `TENANT_SCOPED_COLLECTIONS`, so no cross-tenant leakage is possible by construction.
6. **Provenance is mandatory, not decorative** — every answer cites SQL, metric definition, row counts, date range. Auditability = trust = SOC2 story.

---

## 10. Frontend

New page `/app/projects` (fresh, reusing existing components where they fit):

```
ProjectPage
├─ ProjectHeader (name, problem statement, sync statuses)
├─ SourceSidebar    (bound sources + freshness: last_sync, watermark, status)
├─ CellList         (vertical notebook — problem cell, question/answer cells with provenance)
│   ├─ ProblemCell
│   ├─ QuestionCell  (ask → streams answer via existing chat WS)
│   ├─ AnswerCell    (markdown + provenance footer: SQL, metric def, row counts)
│   └─ ChartCell / TableCell (reuse CanvasCardContent rendering)
└─ JourneyPanel     (Phase C: "what's answered / next pivotal question")
```

- **Store:** new `projectStore.js` (zustand, server-backed — replaces the localStorage-only `canvasStore` for project mode; canvasStore stays for the legacy playground).
- **Launcher:** the datasets page dropdown → a project list ("open a different project" replaces "switch dataset"). Upload auto-creates a project (no extra step).
- **Provenance visible by default:** every AnswerCell renders SQL + metric definition + row counts in a collapsed footer.
- **Connections panel:** the workspace-level connections list (existing connectors UI) is surfaced so binding a source is "pick from what exists," never "set up a new connection" mid-analysis.

---

## 11. V1 scope & phases

| Phase | Ships | Excludes |
|---|---|---|
| **A — Foundation** | Project CRUD + source *binding* (references existing connections) + sync-status + ingestion contract (dedup default ON for project materialization); `journey/next-question` endpoint with MECE decompose + derived-question loop | UI journey panel |
| **B — Cells** | Project UI: problem cell, question/answer cells with provenance, chart/table cells (reuse canvas renderers) | Reactive DAG |
| **C — Journey panel** | "Where you are in this problem, what's answered, next hard question" | — |
| **Phase 2** | Cross-source joins (DuckDB), live mode, scheduled refresh per source | — |

---

## 12. What I verified in the codebase (grounded, not aspirational)

- **No server-side project/canvas persistence exists.** `canvasStore.js` is localStorage-only with a single `linkedDatasetId` (the exact single-dataset model being replaced). Backend code search for canvas/notebook/playground: zero hits.
- **Connections already exist and are workspace-scoped:** `api/databases` (Postgres/MySQL/MongoDB), `api/dlt` (~20 SaaS sources incl. Slack), Google Sheets. All converge to parquet → dataset → profile → semantic layer.
- **Incremental machinery exists:** `services/dlt/state.py` persists high-water marks; each DB connector implements `extract_incremental(increment_column)`.
- **Idempotency exists:** `services/pipeline/process.py` compare-and-swap guard; row-dedup in `services/pipeline/clean.py` is **opt-in today** — flips to default-on for project source materialization.
- **The thinking machinery exists but is dead:** `services/thinker/thinker_agent.py` (`mece_analysis`, chain-of-thought) is imported by nothing. Resurrecting it for the journey-state loop is a wiring task, not a build task.
- **Follow-up suggestions are generic:** `prompts/sql.py get_follow_up_prompt` is an LLM prompt over `current_analysis` — not grounded in findings + journey state. The `journey/next-question` endpoint replaces it.

---

## 13. Open questions (decision-needed later, not blocking Phase A)

1. Project list vs. auto-create-per-upload at launch — proposed: auto-create on upload, project list as the home launcher.
2. Where the project list lives in the sidebar (replacing "Assets" dropdown?).
3. Whether the legacy playground (canvasStore) is deprecated or kept as a freeform surface.
4. Context-source ingestion for documents (PDF → RAG): scope for Phase A (bind + store) vs. Phase B (parse + translate to queries).
