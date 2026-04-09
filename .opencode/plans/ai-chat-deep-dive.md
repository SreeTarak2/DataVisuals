# AI Chat Feature — Deep Dive
**Generated:** 2026-04-09  
**Method:** Full codebase audit (15 files, ~4000 LOC) + 8 targeted WebSearch queries  
**Scope:** "Chat with your data" feature — the conversational analytics pipeline

---

## Part 1: What This Feature Actually Does (Codebase Reality)

### Architecture Map

```
User Input (WebSocket)
    │
    ├─ Prompt Sanitizer (injection protection)
    ├─ Intent Guardrail (off-topic rejection)
    │
    ├─ Query Understanding Pipeline
    │   ├─ Fast archetype detection (explorer/analyst/expert) — rule-based, zero LLM cost
    │   ├─ Vague query detection ("show me something interesting")
    │   ├─ Vocabulary gap detection (mean→median for skew-prone columns)
    │   └─ Full intent engine (LLM call) for underspecified/misspecified queries
    │
    ├─ Routing Decision
    │   ├─ SQL Execution Path (DuckDB) — for data questions → grounded, no hallucination
    │   ├─ QUIS Deep Analysis (LangGraph) — for "deep dive" / correlation / anomaly queries
    │   └─ LLM Conversational Path — for metadata/descriptive/narrative queries
    │
    ├─ Context Assembly
    │   ├─ RAG context (chunked dataset embeddings via FAISS)
    │   ├─ Conversation history (optimized — keeps recent 5 + important older messages)
    │   ├─ Memory service (Mem0-inspired — persists facts across conversations per user+dataset)
    │   └─ Belief store (ChromaDB — subjective novelty detection, "don't repeat what user already knows")
    │
    ├─ LLM Call (OpenRouter → Gemini Flash / Claude / GPT)
    │   ├─ Streaming via WebSocket (token-by-token)
    │   ├─ Adaptive formatting (simple/moderate/complex based on query)
    │   ├─ Archetype-calibrated response style (explorer=plain English, expert=full statistics)
    │   └─ Jargon humanizer (40+ replacements: "correlation"→"link between")
    │
    ├─ Chart Generation (optional, from results or LLM suggestion)
    │   └─ Hydrated via Plotly.js with dataset-aware column matching
    │
    ├─ Post-Processing
    │   ├─ Follow-up suggestions (rule-based, context-aware, 3 chips)
    │   ├─ Data quality notes (outlier/missing value warnings)
    │   ├─ Narrative repair (retry if LLM returned chart-only without text)
    │   └─ Privacy controls (PII redaction based on user settings)
    │
    └─ Persistence
        ├─ Conversation stored in MongoDB (with auto-archiving at 400+ messages)
        ├─ Memory extraction (fire-and-forget: extracts salient facts from exchange)
        └─ Belief store update (passive: boosts related beliefs, ingests new facts)
```

### Key Files

| File | Role | LOC |
|------|------|-----|
| [api/chat/routes.py](version2/backend/api/chat/routes.py) | WebSocket endpoint, image upload, conversation CRUD | 345 |
| [services/ai/ai_service.py](version2/backend/services/ai/ai_service.py) | Core orchestrator — chat processing, SQL routing, streaming | ~1200 |
| [services/ai/query_rewrite.py](version2/backend/services/ai/query_rewrite.py) | Intent detection, archetype classification, query enrichment | 678 |
| [services/query/executor.py](version2/backend/services/query/executor.py) | NL→SQL generation + DuckDB execution (grounded path) | ~500 |
| [services/conversations/conversation_service.py](version2/backend/services/conversations/conversation_service.py) | MongoDB conversation CRUD + auto-archiving | 546 |
| [services/memory/memory_service.py](version2/backend/services/memory/memory_service.py) | Mem0-inspired fact extraction + keyword retrieval | 385 |
| [services/agents/belief_store.py](version2/backend/services/agents/belief_store.py) | ChromaDB-based novelty detection for insights | ~350 |
| [core/prompt_templates.py](version2/backend/core/prompt_templates.py) | All system prompts — McKinsey MECE, SQL gen, chat calibration | ~1200 |
| [pages/chat/ChatPage.jsx](version2/frontend/src/pages/chat/ChatPage.jsx) | Frontend chat page — message list, input, chart rendering | ~800 |
| [components/features/chat/ChatPanel.jsx](version2/frontend/src/components/features/chat/ChatPanel.jsx) | Reusable chat panel with streaming, feedback, history | ~600 |
| [hooks/useWebSocket.js](version2/frontend/src/hooks/useWebSocket.js) | WebSocket connection management + reconnection | ~200 |
| [store/chatStore.jsx](version2/frontend/src/store/chatStore.jsx) | Zustand store — message state, JSON extraction, history | ~300 |

### What's Genuinely Impressive (strengths to preserve)

1. **SQL execution path is grounded** — Data questions go through NL→SQL→DuckDB, not hallucinated by the LLM. This is architecturally correct and addresses the #1 user fear.

2. **Three-tier archetype system** — Explorer/Analyst/Expert detection calibrates response vocabulary and depth. Most competitors don't do this. The prompt engineering here is sophisticated (archetype-specific instruction blocks with clear vocabulary guardrails).

3. **Query understanding pipeline** — Detects underspecified queries ("show me something interesting"), vocabulary gaps (mean→median for price columns), and misspecified intent. Rewrites internally without showing the rewrite to the user. Better than 90% of competitors.

4. **Belief store + novelty detection** — Avoids telling the user things they already know. ChromaDB-backed, with confidence decay. This is a research-grade feature that competitors like ThoughtSpot and Julius don't have.

5. **Memory persistence across conversations** — Mem0-inspired fact extraction means the system learns from interactions and carries context across sessions for the same dataset.

6. **Streaming via WebSocket** — Real-time token streaming with thinking steps ("Loading conversation history", "Executing data query", "Building visualization"). Good UX scaffolding.

---

## Part 2: Research Findings — What Real Users Need

### Search Queries & What They Revealed

| # | Query | Key Finding | Source |
|---|-------|-------------|--------|
| 1 | "text to SQL" natural language accuracy enterprise 2025 | Spider 2.0 benchmark: best model only 31% execution accuracy on enterprise schemas. Enterprise chatbot: only 53% of responses correct. | ACM Survey, AWS ML Blog |
| 2 | AI data chatbot "show your work" audit trail trust 2025 | "You can't ever blindly trust this tool." Leading orgs now require built-in fact validation + audit trails as non-negotiable procurement criteria. | CustomGPT, Parallel HQ |
| 3 | ChatGPT advanced data analysis limitations frustrations | 50MB file limit, Python-only sandbox, no persistent state across sessions, no outbound network requests. | Obot AI, MIT Sloan |
| 4 | Conversational AI "multi-turn" context window limitations | After 20 turns, chatbots start contradicting themselves (Chroma Research, all 18 frontier models). Most drop older messages silently. "Context rot" is a named phenomenon. | Atlan, ProductTalk |
| 5 | "chat with data" tool frustrating wrong answers trust | AI sounds 34% more confident when generating incorrect information. 1 in 3 AI answers are false (2025 study across 10 chatbots). | Euronews, Suprmind |
| 6 | AI analytics "suggested questions" guided exploration UX | 2026 is "the year of AI fatigue." Users don't know what to ask. Best practice: shift from command-based to exploration-based interaction. Help users "recognize what they want progressively." | UX Collective, UX Tigers |
| 7 | Data analysis chatbot export chart share dashboard | Export/share is a table-stakes feature gap. Metabase, Tableau, even Julius offer chart export. The ability to export chatbot data into BI tools is a "valued feature." | Let Data Speak, Botpress |
| 8 | Natural language data query tool wrong chart follow up | Advanced platforms support conversational context for follow-ups. Less mature tools treat each query independently, "limiting usefulness for real-world analytical workflows." | OvalEdge, ChatMaxima |

### The 5 Pain Points Users Actually Have

**Pain 1 — "It gave me a confident wrong answer"**
Text-to-SQL accuracy on real enterprise schemas is 31% (Spider 2.0 benchmark). Even well-built systems have 53% accuracy in production. Users have been burned and now demand to see the underlying logic.

**Pain 2 — "I can't verify anything it told me"**
Audit trails and "show your work" are now non-negotiable in enterprise procurement. Users want to see the SQL, the row count, the filters applied, the sample size — not just the conclusion.

**Pain 3 — "It forgets what I just said"**
After 20 turns, all frontier models start contradicting themselves. "Context rot" is a documented phenomenon. Users expect multi-turn conversations but get frustrated when context degrades.

**Pain 4 — "I don't know what to ask"**
2026 is the year of "AI fatigue." Users stare at a blank chat input and don't know where to start. The best products have shifted from "ask anything" to "choose from these high-value questions" — exploration-based, not command-based.

**Pain 5 — "I can't do anything with what it showed me"**
Charts generated in chat are ephemeral. They can't be exported, embedded, shared, or promoted to a dashboard. This makes the chat a dead-end for anything beyond personal exploration.

---

## Part 3: Gap Analysis — Codebase vs. User Expectations

### 🔴 BLOCKING — User gives up here

**Gap 1: SQL/code is generated but never shown to the user**
- **Codebase:** SQL execution path exists (`query_executor.py`) and generates real SQL. The SQL is even saved to the conversation message: `ai_message["sql"] = result["sql"]` (line 2802). The WebSocket `done` event sends `"sql": result.get("sql")`.
- **Problem:** The frontend `ChatPanel.jsx` and `ChatPage.jsx` have **no UI element to display the SQL**. The `sql` field arrives in the WebSocket payload but is never rendered. The user sees the answer but cannot verify it.
- **Impact:** Directly feeds Pain 1 + Pain 2. The backend solved the trust problem; the frontend doesn't surface the solution.
- **Fix:** Add a collapsible "Show SQL" / "How I got this" panel below AI responses that contain SQL. The data is already there.

**Gap 2: Charts generated in chat cannot be exported or shared**
- **Codebase:** Charts are rendered via Plotly.js inline in `ChatPanel.jsx` (line 92-100). There is no export button, no "save to dashboard" action, no shareable link.
- **Problem:** Every chart is trapped inside the conversation. A user who builds a great visualization through iterative Q&A has no way to use it anywhere else.
- **Impact:** Directly feeds Pain 5. The chat becomes a dead-end for any workflow beyond personal curiosity.
- **Fix:** Add "Download PNG" and "Add to Dashboard" action buttons to chart cards in chat. Plotly.js has built-in `Plotly.downloadImage()` — it's a frontend-only change.

**Gap 3: No onboarding guidance — empty chat with no suggested starting questions**
- **Codebase:** The follow-up suggestion system (`_generate_follow_up_suggestions` at line 56-184) generates context-aware chips **after** a response. But there is no **initial** suggestion system for when a user opens a new conversation with a dataset. The empty state shows a generic prompt.
- **Problem:** Users stare at a blank input box. They don't know what to ask. This is the #1 onboarding friction point for all conversational analytics tools.
- **Impact:** Directly feeds Pain 4. Research shows that exploration-based (not command-based) interfaces outperform blank-slate chat.
- **Fix:** When a new conversation starts, use the dataset metadata (already loaded) to generate 4-6 high-value starter questions. The `get_deep_reasoning_prompt` in `prompt_templates.py` already generates "top 3 business questions a stakeholder would ask" — surface these as clickable chips.

**Gap 4: No way to compare across datasets or time periods**
- **Codebase:** Conversations are scoped to a single `dataset_id` (enforced in `conversation_service.py` line 390-397). There is no mechanism to reference a second dataset, upload updated data into the same conversation, or compare "this month vs last month."
- **Problem:** Real analytics workflows are iterative and comparative. "How does this compare to last quarter?" is one of the first follow-up questions users ask.
- **Impact:** Users who need comparative analysis abandon the chat and do it manually in a spreadsheet.
- **Fix:** Allow uploading a second file into an existing conversation (or referencing another dataset the user owns). The SQL executor already operates on DataFrames — it could join two.

### 🟡 FRICTION — Slows them down but they push through

**Gap 5: "What I understood" clarification card exists in backend but may not render in frontend**
- **Codebase:** The `QueryUnderstanding.what_i_understood` field is generated by the intent engine (`query_rewrite.py` line 297-309) and sent back. There's a `ClarificationCard.jsx` component in the frontend.
- **Problem:** The clarification flow is not consistently surfaced. The `needs_clarification` flag drives it, but for many queries (analyst/expert archetype), the fast path is taken and no clarification is shown. This means the user never sees "Here's what I understood" — they just get an answer and have to trust it.
- **Impact:** Partially feeds Pain 2. Users want to see "I interpreted your question as X" before getting the answer.
- **Fix:** Always show a brief "Understanding: {what_i_understood}" line at the top of AI responses, even on the fast path. It costs nothing (no extra LLM call) and builds trust.

**Gap 6: Memory retrieval uses keyword overlap, not vector similarity**
- **Codebase:** `memory_service.py` line 261: `query_words = set(query.lower().split())` — retrieval is word-intersection scoring. The code even has a comment: "Can be upgraded to vector similarity (FAISS) later."
- **Problem:** Keyword overlap misses semantic matches. "What drives revenue?" won't match a stored memory about "sales growth correlated with marketing spend." The memory system is architecturally sound but functionally shallow.
- **Impact:** The system "forgets" relevant context even though it stored it. Users experience this as the chat not learning from previous conversations.
- **Fix:** Replace keyword overlap with FAISS vector similarity. The project already uses FAISS for RAG (`faiss_vector_service.py` exists). This is a straightforward swap.

**Gap 7: Context window management drops important context silently**
- **Codebase:** `ContextWindowManager.optimize_history()` (ai_service.py line 749) keeps the most recent 5 messages and selectively keeps older chart-bearing messages. Older messages are dropped.
- **Problem:** Research confirms "context rot" after 20 turns (Chroma Research). DataSage's 5-message recency window is aggressive — a user asking their 7th question may lose context from question 1 that's critical for understanding the chain of reasoning.
- **Impact:** Feeds Pain 3. Users notice when the chat forgets something they said 3 questions ago.
- **Fix:** Two improvements: (1) Increase recency window from 5 to 10. (2) Use the memory service to inject a "conversation summary so far" into the prompt (the infrastructure for `conversation_summary` already exists in memory_service.py line 77 but isn't used during chat).

**Gap 8: Follow-up suggestions are rule-based and sometimes generic**
- **Codebase:** `_generate_follow_up_suggestions()` (line 56-184) uses regex intent matching + column metadata to generate 3 follow-ups. Fallbacks are generic: "Visualize this as a chart", "What anomalies exist?"
- **Problem:** When the rule-based path can't infer a good suggestion, the fallbacks are too generic to be useful. They feel like "the AI doesn't know what I should ask next."
- **Impact:** Partially feeds Pain 4. Follow-ups should feel like a smart analyst saying "here's what you should look at next" — not a dropdown of generic options.
- **Fix:** Use the LLM's response content to generate follow-ups (not just the query). If the answer mentioned a surprising finding about a specific column, the follow-up should dig into that column. A lightweight LLM call after the main response (fire-and-forget pattern, like the memory extraction) could generate truly contextual follow-ups.

### 🟢 DELIGHT — Small touches that would make users love it

**Gap 9: No "thinking trace" for complex analyses**
- **Codebase:** Thinking steps exist ("Loading conversation history", "Executing data query") but they describe infrastructure, not reasoning. The McKinsey MECE framework in `prompt_templates.py` generates rich analytical strategy — but it's consumed internally and never shown.
- **Problem:** Users love seeing how the AI thinks. GitHub Copilot's "thinking" mode, ChatGPT's reasoning tokens — the trend is toward transparency. Showing a brief "reasoning trace" would differentiate DataSage.
- **Fix:** Surface a 2-3 line "reasoning preview" during the thinking phase: "Looking at 3 columns: revenue, date, region. Checking for seasonal patterns..." This builds trust and makes wait times feel productive.

**Gap 10: No "pin this insight" or bookmarking within chat**
- **Codebase:** There's a bookmarks API (`api/bookmarks/routes.py`) in the platform, but it's not wired into the chat interface.
- **Problem:** Users discover insights through iterative chat and want to save specific answers. Currently they'd have to screenshot or copy-paste.
- **Fix:** Add a "Pin" button to AI responses. Save pinned insights to the existing bookmarks collection. This creates a curated "findings" list that turns chat from ephemeral to durable.

**Gap 11: No confidence indicator on AI answers**
- **Codebase:** The SQL execution path returns deterministic results (no confidence needed). But the LLM conversational path returns probabilistic text with no signal about confidence level.
- **Problem:** Users can't tell the difference between "I computed this from your data" (high confidence) and "I'm inferring this based on patterns" (lower confidence).
- **Fix:** Tag responses with their source path: "Computed from your data" (SQL path) vs "AI-generated analysis" (LLM path). The routing decision is already made in the code — just surface it.

**Gap 12: Chat-generated charts don't match Charts Studio quality**
- **Codebase:** Chat charts are generated by the LLM's `chart_config` and hydrated via `hydrate_chart()`. Charts Studio has a full format panel (`FormatPanel.jsx`), encoding bar (`EncodingBar.jsx`), and date range control. Chat charts get none of this.
- **Problem:** Charts in chat are second-class citizens — no brand colors, no formatting control, no axis customization.
- **Fix:** Add a "Open in Charts Studio" button that transfers the chart config to the Charts Studio page, pre-filled. The user can then refine formatting. This also bridges the gap between Chat and Charts Studio (identified in the user-reality-check as disconnected features).

---

## Part 4: Prioritized Improvement Plan

Ranked by: **user impact** (how many users hit this × how severely it blocks them)

### Tier 1 — Do This Week (high impact, already half-built)

| # | Improvement | Why It Matters | Effort |
|---|------------|----------------|--------|
| 1 | **Surface the SQL in the frontend** | Backend already generates and sends SQL. Frontend just needs a collapsible panel. Directly addresses the #1 trust crisis in AI analytics. | Frontend only — add `<details>` to ChatMessage when `msg.sql` exists |
| 2 | **Dataset-aware starter questions** | The `get_deep_reasoning_prompt` already generates "top 3 business questions." Show them as clickable chips when opening a new conversation. Eliminates blank-chat paralysis. | One LLM call on conversation create → cache in dataset metadata |
| 3 | **Chart export button (PNG)** | `Plotly.downloadImage()` is a single function call. Currently impossible to get a chart out of chat. | ~20 LOC in ChatPanel.jsx |
| 4 | **Show "Understanding: {what_i_understood}" on all responses** | The data is already computed on every query (fast path returns `_generate_simple_confirmation`). Just render it. | Frontend: add a small text line above AI response |

### Tier 2 — This Month (medium effort, high retention impact)

| # | Improvement | Why It Matters | Effort |
|---|------------|----------------|--------|
| 5 | **"Open in Charts Studio" button** | Bridges Chat ↔ Charts Studio gap. Turns ephemeral chat charts into editable, formattable visualizations. | Pass chart_config as URL state to ChartsStudio route |
| 6 | **Confidence badge: "Computed" vs "AI-inferred"** | Users can't distinguish grounded SQL answers from LLM-generated text. A simple badge ("Verified from data" vs "AI analysis") makes trust explicit. | Tag responses with source_path in the WebSocket payload (routing info already available) |
| 7 | **Upgrade memory retrieval to FAISS vectors** | Current keyword-overlap scoring misses semantic matches. FAISS is already in the project. Makes the system feel like it actually remembers. | Swap scoring function in memory_service.py, add embedding step |
| 8 | **LLM-powered follow-up suggestions** | Replace generic fallbacks with response-aware suggestions. Fire-and-forget after main response, like the memory extraction pattern. | Add async follow-up generation task post-response |
| 9 | **Increase context window to 10 + inject conversation summary** | 5-message recency is too aggressive. Conversation summary infrastructure exists but isn't used. | Increase `keep_recent`, inject `conversation_summary` into prompts |

### Tier 3 — Next Quarter (larger scope, market differentiation)

| # | Improvement | Why It Matters | Effort |
|---|------------|----------------|--------|
| 10 | **Multi-dataset comparison in chat** | "Compare this month vs last month" is one of the most natural follow-ups. Currently impossible because conversations are single-dataset scoped. | Backend: allow optional second dataset_id; SQL executor: JOIN support |
| 11 | **Reasoning trace during thinking phase** | Differentiation move. Show "Looking at revenue × region × date. Hypothesis: seasonal pattern in Q4" during the loading state. | Surface internal reasoning from MECE prompt as streaming tokens |
| 12 | **Pin/bookmark insights from chat** | Bookmarks API exists but isn't wired to chat. Turns ephemeral chat into a durable findings system. | Wire ChatMessage "pin" button to existing bookmarks API |

---

## Part 5: The One Architectural Insight

DataSage's AI Chat has a rare advantage that's being wasted: **it already executes real SQL against real data for analytical questions.** This is the grounded, non-hallucinating path that every competitor is trying to build. The SQL is generated, validated, executed, and the results are formatted.

But the user never sees the SQL. They never see the row count. They never see that their answer came from actual computation rather than LLM confabulation.

The single highest-ROI change is not building a new feature — it's **surfacing what already exists.** Show the SQL. Show "Computed from 2,847 rows." Show "Filtered by: date > 2025-01-01." Turn the trust gap from a liability into a competitive moat.

Every competitor talks about "AI-powered analytics." DataSage can be the one that says: **"Here's exactly how I got this answer."**

---

*Research sources: ACM Computing Surveys (text-to-SQL survey), AWS ML Blog (enterprise NL-to-SQL), Atlan (context window limitations), ProductTalk (context rot), Euronews (AI hallucination study), Suprmind (hallucination statistics 2026), UX Collective (AI UX patterns), UX Tigers (intent discovery), Parallel HQ (chatbot trust UX), CustomGPT (business chatbots 2026), OvalEdge (conversational analytics platforms), ChatMaxima (conversational AI 2026)*
