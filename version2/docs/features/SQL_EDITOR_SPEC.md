# DataSage AI-Assisted SQL Editor — Product Spec

## 1. Problem Statement

DataSage currently generates SQL and displays it in the chat panel, but users cannot:
- **Edit** the SQL and re-run it
- **Write** SQL from scratch with AI assistance
- **Debug** SQL errors with AI help
- **Save** useful SQL snippets as governed metrics

The semantic pipeline (`MetricSQLCompiler`) generates deterministic SQL, but power users need an **escape hatch** to verify, tweak, and own their queries.

## 2. Industry Research Summary

### Hex Magic
- **AI invoked via** `Cmd+Shift+M` prompt bar between notebook cells
- **Inline ghost text**: AI suggests completions as user types (Copilot-style)
- **Schema context**: `@`-mention datasets/tables to scope the AI
- **Error fixing**: Highlight broken SQL → "Fix this" → AI suggests repair
- **Explain**: Natural language breakdown of any query

### Mode AI Assist
- **AI in sidebar**: Side pane on the right of the SQL editor
- **Natural language annotations**: `--! total sales by region` → AI fills in SQL for that comment
- **Shortcuts**: `Shift+Opt+N` generate, `Shift+Opt+I` insert
- **Session history**: Shows previous AI generations for the current session

### dbt Cloud (Fusion Engine)
- **Project-aware**: Understands the full dbt DAG, models, macros, YAML
- **Rust-based compiler**: Ultra-fast IntelliSense, schema-aware autocomplete
- **Copilot**: `Cmd+B` to trigger AI actions (debug, explain, refactor)

### Databricks AI SQL Editor
- **Autocomplete**: Ghost text as you type, `Tab` to accept
- **Assistant panel**: Conversational sidebar that writes SQL into the editor
- **Error integration**: Show error → ask AI → get fix in context
- **Dual mode**: Inline completions + chat sidebar

### Common Patterns (the "Standard")
| Pattern | All 4 platforms agree on |
|---------|------------------------|
| **Editor-first** | SQL editor is the primary interface. AI is a copilot inside it. |
| **Inline completions** | Ghost text autocomplete as user types |
| **Draft from NL** | User describes intent → AI generates SQL into editor |
| **Debug with AI** | Highlight error → AI suggests fix |
| **Explain query** | AI explains SQL in plain English |
| **Schema browser** | Column list + search panel alongside editor |
| **Edit → Run → Results** | The fundamental loop |

## 3. DataSage Implementation Plan

### Phase 1: SQL Viewer → Editor (MVP — 1-2 sessions)

**Goal**: Replace the read-only SQL display with an editable workspace.

#### Frontend Changes

**3.1.1 Install editor dependency**
```bash
# CodeMirror 6 — lighter than Monaco (200KB vs 2MB+)
npm install @codemirror/view @codemirror/state @codemirror/lang-sql @codemirror/commands @codemirror/autocomplete @codemirror/language @codemirror/theme-one-dark @codemirror/search codemirror
```

**3.1.2 New component: `SqlEditor.jsx`**
```
frontend/src/components/features/sql/
  SqlEditor.jsx          # Core editor with CodeMirror
  SqlEditorToolbar.jsx   # Run, Explain, Fix buttons
  SqlResultTable.jsx     # Results display (reuse from ChatPanel)
  SqlEditorPanel.jsx     # Full panel wrapper (sidebar or modal)
```

**3.1.3 SqlEditor component API**
```jsx
<SqlEditor
  initialSql="SELECT ..."      // Pre-populated SQL
  datasetId="abc123"           // For schema context + execution
  readOnly={false}             // Allow editing
  onRun={(sql) => ...}         // Execute callback → returns results
  onSaveAsMetric={(sql) => ...} // Promote to governed metric
  height="300px"
  showSchema={true}            // Toggle schema browser panel
/>
```

**3.1.4 Integration with ChatPanel**
- Add **"Edit SQL"** icon button next to AI messages that have `render_intent.show_sql === true`
- Clicking opens a slide-out panel or inline editor below the message
- User edits SQL → clicks **Run** → results appear below
- User clicks **Save as Metric** → opens metric definition dialog

#### Backend Changes

**3.1.5 New API endpoint: `POST /api/v2/query/execute`**
```json
// Request
{
  "dataset_id": "abc123",
  "sql": "SELECT region, SUM(revenue) FROM data GROUP BY region",
  "limit": 1000
}

// Response
{
  "success": true,
  "data": [{"region": "North", "SUM(revenue)": 52000}, ...],
  "columns": ["region", "SUM(revenue)"],
  "row_count": 5,
  "execution_time_ms": 45
}
```

**3.1.6 Wire backend endpoint**
- Reuse `QueryExecutor.execute_sql()` from `services/query/executor.py`
- Add validation via `SQLValidator.validate()` first
- No LLM involved — just DuckDB execution
- Rate-limited (same as chat)

---

### Phase 2: AI Assistance in the Editor (2-3 sessions)

**Goal**: Add the three core AI features: Draft from NL, Explain, Fix.

#### 3.2.1 "Generate" — Draft SQL from natural language

**UX**: User clicks **"Generate"** button → text input appears → types description → AI generates SQL into editor

```jsx
// Inside SqlEditorToolbar
<button onClick={openGenerateInput}>
  <Sparkles size={14} /> Generate
</button>
// → inline input: "show me total revenue by region for 2024"
// → calls POST /api/v2/semantic/query with { query: "...", return_raw: true }
// → extracts .sql from response → inserts into editor
```

**Backend**: Reuse `SemanticQueryService.execute()` which already:
1. Extracts intent via `IntentExtractor`
2. Validates via `validate_intent()`
3. Compiles via `MetricSQLCompiler`
4. Returns `{ sql, data, response }`

Set `return_raw: true` so it returns the SQL + data without NL interpretation.

#### 3.2.2 "Explain" — Natural language breakdown of SQL

**UX**: User clicks **"Explain"** → AI returns plain English explanation of what the SQL does

```jsx
<button onClick={explainSql}>
  <MessageSquare size={14} /> Explain
</button>
// → calls POST /api/v2/sql/explain with { sql, dataset_id }
// → returns { explanation: "This query calculates total revenue..." }
```

**Backend**: New lightweight endpoint or LLM call:
```python
async def explain_sql(sql: str, dataset_id: str) -> str:
    prompt = f"""Explain this SQL query in plain English.
Focus on what it computes, what filters it applies, and what business question it answers.

SQL:
{sql}

Return a concise 2-3 sentence explanation."""
    return await llm_router.call(prompt, model_role="intent_engine", ...)
```

#### 3.2.3 "Fix" — Debug SQL errors

**UX**: Query fails → error shown → user clicks **"Fix with AI"** → AI suggests corrected SQL

```jsx
// In SqlEditorPanel, when execution fails:
<div className="sql-error">
  <AlertTriangle size={14} />
  <span>{error}</span>
  <button onClick={fixSql}>Fix with AI</button>
</div>
```

**Backend**: Reuse `SQLRepairAgent` from `services/query/sql_repair_agent.py`
```python
repair_result = await sql_repair_agent.repair(
    sql=original_sql,
    error_msg=exec_error,
    df=df,
    original_query=user_description,  # optional but helpful
    schema_block=column_schema,
)
# repair_result.was_repaired → show diff
# repair_result.sql → insert into editor
```

#### 3.2.4 Inline Autocomplete (Future)

The AI suggests completions as the user types:

```javascript
// Using CodeMirror 6 autocomplete + a custom source
import { sql } from '@codemirror/lang-sql';
import { autocompletion } from '@codemirror/autocomplete';

const aiCompletionSource = (context) => {
  const word = context.matchBefore(/\w*/);
  if (!word || word.from === word.to && !context.explicit) return null;
  
  // 1. First: schema-aware completions (column names, table references)
  const schemaCompletions = getSchemaCompletions(context.state);
  
  // 2. Optionally: AI-predicted next tokens (latency-sensitive)
  //    Only if the user is idle for >500ms
  if (userHasBeenIdle) {
    return fetchAiCompletion(context.state.doc.toString(), cursorPosition);
  }
  
  return { from: word.from, options: schemaCompletions };
};

new EditorView({
  extensions: [
    sql(),
    autocompletion({ override: [aiCompletionSource] }),
  ],
});
```

**This is Phase 3 material** — requires a low-latency endpoint and careful UX
to avoid suggesting wrong SQL inline.

---

### Phase 3: Schema Browser + Save as Metric (2 sessions)

**Goal**: Complete the power user workflow.

#### 3.3.1 Schema Browser Panel

```
┌─────────────────────────────┐
│ 🔍 Search columns...        │
│                             │
│ 📊 Tables (if joined)       │
│   └─ data                   │
│      ├─ region (string)     │
│      ├─ revenue (float)     │ ← clickable → inserts into editor
│      ├─ profit (float)      │
│      └─ date (date)         │
│                             │
│ 📐 Defined Metrics          │
│   ├─ Profit Margin          │ ← clickable → inserts definition
│   └─ YoY Growth             │
└─────────────────────────────┘
```

Reuse `DataPanel.jsx` from ChartsStudio (already has column list UI).

#### 3.3.2 "Save as Metric" Flow

User writes/crafts SQL → clicks **"Save as Metric"** → opens dialog:

```
┌─────────────────────────────────┐
│ Define Metric                   │
│                                 │
│ Name:     [Net Profit]          │
│ Formula:  [revenue - cost]      │
│ (extracted from SQL or manual)  │
│                                 │
│ Source:   [column_name | custom]│
│                                 │
│ Description: [optional]         │
│                                 │
│ ┌─────────────────────────┐     │
│ │ Preview: SUM(revenue) - │     │
│ │ SUM(cost)               │     │
│ └─────────────────────────┘     │
│                                 │
│ [Cancel]  [Save to Definitions] │
└─────────────────────────────────┘
```

**Backend**: Reuse `MetricDefinitionStore.upsert_definition()`

---

## 4. Wireframe: SQL Editor in ChatPanel

```
┌────────────────────────────────────────────┐
│ Chat Panel                              │
├────────────────────────────────────────────┤
│                                            │
│  User: "Show me revenue by region"         │
│                                            │
│  AI: Here's the revenue breakdown...       │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │ SQL  [Edit] [Explain] [Run]       │    │
│  │ SELECT region, SUM(revenue)       │ ← click [Edit] opens editor
│  │ FROM data                         │    │
│  │ GROUP BY region                   │    │
│  └────────────────────────────────────┘    │
│                                            │
│  [User clicks Edit]                        │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │ [▶ Run] [✨ Gen] [💬 Explain] 🔧 Fix│   │
│  │ ────────────────────────────────── │    │
│  │ SELECT region, SUM(revenue)        │ ← editable CodeMirror
│  │ FROM data                          │    │
│  │ WHERE year = 2024                  │ ← user added this filter
│  │ GROUP BY region                    │    │
│  │ ORDER BY SUM(revenue) DESC         │    │
│  │ ────────────────────────────────── │    │
│  │                                    │    │
│  │ [Results: 5 rows, 45ms]           │    │
│  │ ┌─────────────────────────────┐   │    │
│  │ │ region   │ SUM(revenue)    │   │    │
│  │ │ North    │ $52,000         │   │    │
│  │ │ South    │ $41,000         │   │    │
│  │ └─────────────────────────────┘   │    │
│  │                                    │    │
│  │ [Save as Metric]                   │    │
│  └────────────────────────────────────┘    │
└────────────────────────────────────────────┘
```

---

## 5. Implementation Order

| Phase | What | Effort | Dependencies | Value |
|-------|------|--------|-------------|-------|
| **P1a** | `SqlEditor.jsx` component (read-only → editable) | 1 session | Install CodeMirror | High — unblocks everything |
| **P1b** | `POST /api/v2/query/execute` endpoint | 1 session | `QueryExecutor.execute_sql()` | High — allows user to run SQL |
| **P1c** | Wire "Edit SQL" button in ChatPanel | 1 session | P1a + P1b | High — first usable version |
| **P2a** | "Generate from NL" button → inserts SQL into editor | 1 session | `SemanticQueryService` | Medium — core AI feature |
| **P2b** | "Explain this SQL" → LLM explanation | 0.5 session | `llm_router` | Medium — builds trust |
| **P2c** | "Fix with AI" → error → AI repair | 1 session | `SQLRepairAgent` | Medium — reduces frustration |
| **P3a** | Schema browser panel | 1 session | Reuse `DataPanel.jsx` | Medium — power user feature |
| **P3b** | "Save as Metric" → definition store | 1 session | `MetricDefinitionStore` | High — closes the loop |
| **P3c** | Inline autocomplete | 2 sessions | Low-latency endpoint | Low — nice-to-have |

**Total: ~8-10 sessions for full implementation**

---

## 6. Key Design Decisions

1. **CodeMirror 6 over Monaco**: 200KB vs 2MB bundle size. CodeMirror is more modular and has excellent SQL language support. We already use `react-syntax-highlighter` for display — CodeMirror adds editability without a huge dependency cost.

2. **Editor opens inline in chat, not full-page**: Users come to the chat panel to ask questions. The SQL editor should feel like an extension of the chat, not a separate tool. Hex and Mode both embed editing in the notebook/chat flow.

3. **AI features are explicit buttons, not automatic**: Users click "Generate" when they want AI help. No auto-suggesting while typing (in Phase 1-2). This avoids the trust problem of AI writing SQL that the user didn't ask for. Inline autocomplete is Phase 3.

4. **The editor is always connected to a dataset**: The `dataset_id` is required for schema context, column autocomplete, and execution. No standalone "write SQL without data" mode.

5. **Read-only by default, editable on demand**: AI-generated SQL starts read-only in the chat. User clicks "Edit" to make it editable. This prevents accidental edits while keeping the power user path one click away.

---

## 7. Files to Create/Modify

### New Files
```
frontend/src/components/features/sql/
  SqlEditor.jsx               # CodeMirror 6 wrapper
  SqlEditorToolbar.jsx         # Run / Generate / Explain / Fix buttons
  SqlEditorPanel.jsx           # Full editor + schema + results
  SqlResultTable.jsx           # Results display (reuse pattern from ChatPanel)

backend/api/sql/
  __init__.py                  # Router init
  routes.py                    # POST /execute, POST /explain, POST /fix

backend/services/sql/
  __init__.py
  explain_service.py           # LLM-based SQL explanation
  editor_executor.py           # Thin wrapper around QueryExecutor.execute_sql()
```

### Modified Files
```
frontend/src/components/features/chat/ChatPanel.jsx
  → Add "Edit SQL" button next to messages with show_sql=true
  → Wire SqlEditorPanel as slide-out or inline section

frontend/src/services/api.js
  → Add executeSql(), explainSql(), fixSql() API methods

backend/main.py
  → Register sql_router at /api/v2

backend/services/semantic/semantic_query_service.py
  → Expose return_raw path for "Generate from NL" feature
```
