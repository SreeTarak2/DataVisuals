# DataSage AI — Chat Pipeline Architecture Summary

> Last updated: July 29, 2026
> 
> This document captures all chat pipeline improvements made during the architecture cleanup.
> Read this before starting new chat work to understand the current state.

---

## Table of Contents

1. [Architecture Cleanup (What Was Removed)](#1-architecture-cleanup)
2. [Current Chat Pipeline Flow](#2-current-chat-pipeline-flow)
3. [File Map](#3-file-map)
4. [Guard System](#4-guard-system)
5. [Query Understanding](#5-query-understanding)
6. [ReAct Agent (ChatAgent)](#6-react-agent-chatagent)
7. [Synthesis Prompt](#7-synthesis-prompt)
8. [Quality Gate](#8-quality-gate)
9. [Key Decisions](#9-key-decisions)
10. [What Still Needs Work](#10-what-still-needs-work)

---

## 1. Architecture Cleanup

### Deleted (Dec 2025–July 2026)

| File/Directory | Lines | Reason |
|----------------|-------|--------|
| `services/ai/ai_service.py` | ~2800 | Replaced by `services/chat/pipeline.py` |
| `services/ai/copilot_service.py` | ~500 | Replaced by `services/chat/pipeline.py` |
| `services/copilot/` **entire directory** | ~2500 | Dead after copilot_service.py deletion: 11 files + 6 executors |
| `services/llm_router.py` (shim) | ~5 | Replaced by direct import `from llm.router import llm_router` |
| `services/query_executor.py` (shim) | ~5 | Replaced by direct import `from services.query.executor import ...` |
| `services/audit_service.py` (shim) | ~5 | Replaced by direct import `from services.audit import ...` |
| `services/chat/synthesis.py` (shim) | ~5 | Replaced by `prompts/chat.py` |
| `services/chat/guards.py` (shim) | ~5 | Replaced by `prompts/guards.py` |
| `core/prompt_templates.py` | ~500 | Migrated to `prompts/` directory |
| `core/narrative_prompts.py` | ~200 | Migrated to `prompts/narrative.py` |
| `services/ai/multi_agent_orchestrator.py` | ~300 | Dead — canonical version at `services/multi_agent/orchestrator.py` |

### Deduplicated

| What | Dead copy removed | Canonical location |
|------|-------------------|-------------------|
| `ARCHETYPE_INSTRUCTIONS` | `services/ai/query_rewrite.py` | `prompts/_identity.py` |

### Dead code confirmed but NOT yet removed

- `services/ai/ai_designer_service.py` — still referenced by some routes
- `services/ai/kpi_domain.py` — may still be in use

---

## 2. Current Chat Pipeline Flow

```
User → WebSocket (api/chat/routes.py)
         │
         ▼
   Step 1: Off-topic Guard ──────────── redirect ──► ChatResult(redirect_message)
   (prompts/guards.py: check_off_topic)           (zero LLM cost)
         │ passes
         ▼
   Step 2: Load Context ─────────────── error ──► ChatResult(error_message)
   (services/chat/context_loader.py)   (parallel: dataset + RAG + memory + privacy)
         │ success
         ▼
   Step 3: Scope Guard ──────────────── redirect ──► ChatResult(redirect_message)
   (prompts/guards.py: check_scope)               (checks data terms + column names)
         │ passes
         ▼
   Step 4: Query Understanding ──────── timeout ──► ChatResult(raw_query)
   (services/ai/query_rewrite.py:      (LLM call: intent_engine model)
    understand_query())
         │ returns QueryUnderstanding
         ▼
   Step 5: Routing Check ────────────── conversational ──► redirect
         │ sql / metadata
         ▼
   Step 6: ReAct Agent ──────────────── error logged, continues
   (agents/chat/chat_agent.py)         (tools: sql, stats, rag, memory)
         │ returns observations[]
         ▼
   Step 7: Synthesis ────────────────── LLM call, quality gate, retry
   (prompts/chat.py:                   (model_role: narrative_story)
    build_synthesis_prompt →            max_tokens: 768)
    llm_router.call() →
    check_response_quality())
         │ passes / retried
         ▼
   Step 8: Normalize
   (normalize_response_style + humanize_text)
         │
         ▼
   Step 9: Persist + Background Tasks
   (save conversation, memory extraction, belief update, response reflection)
         │
         ▼
   ChatResult(response_text, conversation_id, query_context, quality_issues)
```

### Streaming Path

Same flow through Step 6, then streams synthesis tokens via `_synthesize_streaming()`.  
Quality gate runs at end (log only — can't regenerate streaming output mid-stream).

---

## 3. File Map

### Entry Points

| File | Purpose |
|------|---------|
| `api/chat/routes.py` | WebSocket handler — calls `chat_pipeline.process()` / `.process_streaming()` |
| `api/datasets/routes.py` | REST endpoint `process_dataset_chat` — calls `chat_pipeline.process()` |

### Core Pipeline

| File | Purpose |
|------|---------|
| `services/chat/pipeline.py` | `ChatPipeline` — unified orchestrator (~400 lines) |
| `services/chat/models.py` | `ChatResult`, `ContextPackage`, `QueryContext`, `GuardResult` dataclasses |
| `services/chat/context_loader.py` | Parallel context loading: dataset metadata, RAG, memory, privacy |
| `services/chat/__init__.py` | Exports `ChatPipeline`, `chat_pipeline` singleton |

### Guards

| File | Purpose |
|------|---------|
| `prompts/guards.py` | `check_off_topic()`, `check_scope()` — both zero LLM cost (vocabulary + regex) |

### Query Understanding

| File | Purpose | Status |
|------|---------|--------|
| `services/ai/query_rewrite.py` | `understand_query()` — intent detection + enrichment + routing | ✅ Canonical |
| `services/semantic/intent_extractor.py` | `IntentExtractor.extract()` — structured `QueryIntent` for SQL compilation | ✅ Active, different purpose |
| `prompts/sql.py` | `REWRITE_SYSTEM_PROMPT` — used by `query_rewrite.py` | ✅ Active |
| `prompts/_identity.py` | `ARCHETYPE_INSTRUCTIONS` — explorer/analyst/expert calibration | ✅ Canonical |

### Agent

| File | Purpose |
|------|---------|
| `agents/chat/chat_agent.py` | `ChatAgent` — ReAct loop with 4 tools: sql, stats, rag, memory |
| `agents/base_agent.py` | `BaseAgent` — injection guard, concurrency, budget, circuit breaker |
| `agents/agent_utils.py` | `build_synthesis_snippets()` — formats observations for prompt |

### Synthesis

| File | Purpose |
|------|---------|
| `prompts/chat.py` | `build_synthesis_prompt()`, `check_response_quality()`, `normalize_response_style()`, `humanize_text()` |
| `prompts/_identity.py` | `IDENTITY`, `PERSONA`, `SAFETY_RULES`, `TONE_RULES`, `ARCHETYPE_INSTRUCTIONS` |

### LLM Router

| File | Purpose |
|------|---------|
| `llm/router.py` | `llm_router` singleton — model selection, fallback, token budgeting |

### Background Tasks

| File | Purpose |
|------|---------|
| `services/memory/memory_service.py` | Memory extraction from chat responses |
| `agents/belief/belief_store.py` | PassiveBeliefIngestion — updates belief store from chat |
| `services/insight_reflection/reflector.py` | Response reflection — self-improvement loop |

---

## 4. Guard System

Two-layer defense with zero LLM cost (vocabulary + regex matching):

### Layer 1: `check_off_topic(query)`

Catches: greetings, chit-chat, general knowledge questions, metadata-only queries.

- Pattern matching against `_OFF_TOPIC_PATTERNS` (14 compiled regex patterns)
- Phrase matching against `_CONVERSATIONAL_VOCAB` (13 phrases)
- Short-query rejection (< 5 chars)
- **Cost:** ~microseconds per check

### Layer 2: `check_scope(query, dataset_id, column_names)`

Catches queries that pass the off-topic guard but don't reference any data-related terms or known column names. Runs **after** context loading (so we have `column_names`).

- Checks against `data_terms` set (show, compare, analyze, trend, revenue, etc.)
- Checks against known column names (passed from context_loader)
- Short queries (≤6 words) without data terms → blocked
- Longer queries without data terms → allowed (might be complex analytical questions)
- **Cost:** ~microseconds per check

### Flow:

```
check_off_topic(query)  ──blocked──► redirect message
        │ passed
        ▼
  [load context — get column_names]
        │
        ▼
check_scope(query, dataset_id, column_names)  ──blocked──► redirect message
        │ passed
        ▼
  [query understanding — costly LLM call]
```

---

## 5. Query Understanding

### `services/ai/query_rewrite.py` — `understand_query()`

Two paths:

**Fast path** (for clear, well-specified queries by analyst/expert users):
1. Rule-based archetype detection (`_fast_archetype`) — no LLM
2. Rule-based routing (`_fast_routing`) — metadata vs sql
3. Lightweight LLM enrichment call (`rewrite_engine` model)
4. Validation + post-processing

**Full intent path** (for vague, misspecified, or explorer queries):
1. Fast archetype + vague/vocab-gap detection (rule-based)
2. Full LLM intent detection (`intent_engine` model) — produces enriched_query, what_i_understood, failure_mode, archetype, routing
3. Post-validation — catches: SQL in output, too-short rewrites, answer-pattern indicators, too-long rewrites
4. Fallback to enrichment-only on LLM failure

### `services/semantic/intent_extractor.py` — `IntentExtractor.extract()`

Separate purpose: translates NL query to structured `QueryIntent` (metrics[], dimensions[], filters[]) for the semantic SQL compilation pipeline. Not used for chat — used by `semantic_query_service.py`.

---

## 6. ReAct Agent (ChatAgent)

### Tool Injection

`ChatAgent.__init__()` injects real service singletons into `BaseAgent`:

| Tool | Singleton | Methods used |
|------|-----------|-------------|
| `sql` | `services.query.executor.query_executor` | `execute_query(query, df, dataset_id)` |
| `stats` | `object()` (dummy) | Handler uses direct inline imports |
| `rag` | `services.datasets.faiss_vector_service.faiss_vector_service` | `search_similar_queries(query, user_id, k)` |
| `memory` | `agents.belief.belief_store.get_belief_store()` | `calculate_semantic_surprisal()`, `add_belief()` |

### Duplicate Synthesis Fix

`ChatAgent` overrides `_synthesize()` and `_synthesize_streaming()` with cheap placeholders that join observation snippets with " | ". The authoritative synthesis with quality gate + retry runs in `ChatPipeline._synthesize()`. This avoids **2 LLM calls per message** (was calling agent's internal synthesize + pipeline's synthesize).

### BaseAgent Safety Features

- **Prompt injection guard** — `sanitize_and_validate()` before any run
- **Concurrency limit** — `agent_concurrency_limiter.try_acquire()` rejects if busy
- **Token budget** — `get_run_budget()` / `return_run_budget()`
- **Circuit breaker** — `BreakerRegistry` gates tool calls
- **Agent timeout** — `asyncio.timeout(settings.AGENT_RUN_TIMEOUT)`
- **Audit logging** — fire-and-forget audit entries per agent run

---

## 7. Synthesis Prompt

`prompts/chat.py` → `build_synthesis_prompt()`

### Parameters

```
query                 — User's enriched question
snippets              — Formatted observation snippets from agent
archetype             — "explorer" | "analyst" | "expert"
conversation_context  — Optional last 2 user+AI turns for continuity
```

### Prompt Structure (7 Rules)

1. **BLUF (Bottom Line Up Front)** — Answer first. First 5 words must contain a number or the answer. 9 explicit forbidden openers listed.

2. **Structure** — 3 paragraphs max: headline → supporting detail → next step.

3. **Language Rules — Zero tolerance** — Jargon replacement table (9 categories). Banned words must be replaced with plain English equivalents.

4. **Numbers & Data Citation** — Bold key numbers with `**double asterisks**`. First number MUST be bolded. Every number needs context (e.g., "**18%** — nearly 1 in 5"). Claims must mention which column/field the data comes from.

5. **Confidence & Honesty** — No hedging: ban "I think", "probably", "seems". State findings confidently or explicitly say data is inconclusive.

6. **Self-Check** — 9 checkboxes: direct answer, no generic openers, first number bolded, ≥2 bolded numbers, no banned jargon, clear conclusion, no generic phrases, data cited per claim, no hedging.

7. **Scope Boundary** — Only answer from data. Don't answer general knowledge questions. Never fabricate data.

### Archetype Instructions

From `prompts/_identity.py`:

| Archetype | Tone | Length | Vocabulary |
|-----------|------|--------|------------|
| **Explorer** | Warm, direct, non-condescending | 80–150 words | Zero jargon. Translate everything |
| **Analyst** | Peer-to-peer, confident | 150–250 words | Data terms OK. Translate stats jargon once |
| **Expert** | Direct, precise, peer-level | Match complexity | Full statistical vocabulary expected |

---

## 8. Quality Gate

`prompts/chat.py` → `check_response_quality(response)`

Rule-based (zero LLM cost). Returns `Dict` with `passed`, `issues`, and diagnostic fields.

### Checks (in order)

| # | Check | Details |
|---|-------|---------|
| 1 | **Banned jargon** | Matches against `_BANNED_JARGON` set (~25 terms) |
| 2 | **Generic AI phrases** | Matches against `_GENERIC_PATTERNS` list (~18 patterns like "the data reveals") |
| 3 | **Number count** | Must have ≥2 numbers via regex |
| 4 | **Minimum length** | Must be ≥15 words |
| 5 | **BLUF violation** | First 100 chars checked against `_BLUF_VIOLATIONS` list (9 patterns) |
| 6 | **Bolded numbers** | Regex `\*\*[^*]*\d[^*]*\*\*` — must have ≥1 bolded segment containing a digit (handles `**18%**`, `**$2.1M**`, `**34% of total**`) |
| 7 | **Hedging language** | Matches against `_HEDGING_PATTERNS` list (14 patterns: "i think", "probably", "seems to", "might be") |
| 8 | **Filler word start** | Checks first word (stripped of punctuation) against FILLER_WORDS set: well, so, okay, first, now, regarding |

### Retry on Failure (non-streaming only)

If quality fails, the pipeline appends a fix prompt with the specific issues and retries the LLM call once. If retry also fails, the original response is returned.

### Return value

```python
{
    "passed": bool,
    "issues": List[str],       # Human-readable issue descriptions
    "jargon_found": List[str],
    "number_count": int,
    "bolded_numbers": int,     # Count of bolded segments with digits
    "hedging_found": List[str],
}
```

---

## 9. Key Decisions

### Why one pipeline instead of two services?

The old architecture had `ai_service` (non-streaming) and `copilot_service` (streaming) with duplicated logic, different prompt chains, and inconsistent routing. The unified `ChatPipeline` has a single flow with shared steps 1-5, then diverges only at the synthesis step (batch vs stream).

### Why no LLM in guards?

The off-topic and scope guards use vocabulary + regex matching exclusively (~microseconds). This avoids LLM latency and cost for obvious out-of-scope queries. The LLM-based query understanding (Step 4) handles nuanced routing.

### Why override ChatAgent._synthesize()?

`BaseAgent.run()` always calls `_synthesize()` at the end. But `ChatPipeline.process()` also calls its own `_synthesize()` with the quality gate + retry. Without the override, every chat message would make **2 LLM calls**: one wasted agent synthesis + one authoritative pipeline synthesis.

### Why both guards before query understanding?

1. Off-topic guard — catches obvious greetings/chit-chat before any work
2. Load context — provides `column_names` for scope check
3. Scope guard — catches queries with no data terms (avoids expensive LLM call)
4. Query understanding — only runs for legitimate data queries

### Why increase max_tokens from 512 to 768?

The prompt asks for 3 paragraphs with specific formatting rules. 512 tokens (~380 words) was constraining the model's ability to follow all rules simultaneously. 768 provides enough room for a well-structured BLUF answer.

### Why conversation context?

Without previous messages, the model repeats answers to similar questions. The `_build_conversation_context()` method extracts the last 2 user+AI turns and passes them to the synthesis prompt with a "don't repeat these" instruction.

---

## 10. What Still Needs Work

### Architecture

- [ ] **`services/ai/ai_designer_service.py`** — still has callers; needs review
- [ ] **`services/ai/kpi_domain.py`** — may still be in use
- [ ] **`services/ai/__init__.py`** — still exports `ai_designer_service`; clean up after above

### Chat Quality

- [ ] **Frontend bold rendering** — Does the chat UI properly render `**bold**` markdown or does it show raw asterisks?
- [ ] **Conversation context for streaming** — `_synthesize_streaming()` now receives context but `llm_router.call_streaming()` doesn't take `max_tokens` param — verify streaming quality is comparable
- [ ] **Regenerate/versioning** — Conversation versioning system (message tree) was implemented but frontend integration may not be complete
- [ ] **Follow-up suggestions** — Not currently generated by the synthesis; `chat_pipeline.process()` doesn't produce them

### Testing

- [ ] **Quality gate unit tests** — `prompts/chat.py::check_response_quality()` has no dedicated test file
- [ ] **Guard test suite** — `prompts/guards.py::check_off_topic()` and `check_scope()` have no tests
- [ ] **Pipeline integration test** — End-to-end test for the full pipeline

### Monitoring

- [ ] **Quality gate pass rate** — Track what % of responses pass on first try vs retry
- [ ] **Most common quality issues** — Which checks fail most often? (hedging? jargon? BLUF?)
- [ ] **Archetype distribution** — What % of users are explorer vs analyst vs expert?

---

## Appendix: Old vs New Architecture

### Before (2 services + 2 shims + dead copilot)

```
api/chat/routes.py ──► ai_service.py (non-streaming)
                    └─► copilot_service.py → copilot/ (11+ files)
                    
api/datasets/routes.py ──► ai_service.py
                         └─► copilot_service.py

Backward-compat shims:
  services/llm_router.py ──► llm.router
  services/query_executor.py ──► services.query.executor
  services/audit_service.py ──► services.audit
  services/chat/synthesis.py ──► prompts/chat
  services/chat/guards.py ──► prompts/guards
  core/prompt_templates.py ──► prompts/*
  core/narrative_prompts.py ──► prompts/narrative
```

### After (unified pipeline)

```
api/chat/routes.py ──► ChatPipeline.process() / .process_streaming()
api/datasets/routes.py ──► ChatPipeline.process()

Single flow: guards → context → understand → route → agent → synthesize → persist
```

---

*End of Architecture Summary*
