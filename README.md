# DataSage - Context-Aware AI Analytics Platform

> **Status:** Architecture Research Complete | Ready for Implementation
> **Last Updated:** April 2026

---

## Executive Summary

DataSage is building a context-aware AI analytics platform that solves the 80% problem no competitor addresses: capturing, maintaining, and surfacing business context automatically. This README documents the market research, technical architecture, and implementation strategy.

**The Core Bet:** Build the first analytics tool where context documentation is automatic (a byproduct of use), not manual. Every user interaction makes the system smarter — corrections become rules, query patterns become templates, and insights compound over time.

---

## Table of Contents

1. [Market Research](#1-market-research)
2. [The Problem Space](#2-the-problem-space)
3. [Competitive Landscape](#3-competitive-landscape)
4. [Technical Architecture](#4-technical-architecture)
5. [Build Order](#5-build-order)
6. [Risks & Mitigation](#6-risks--mitigation)

---

## 1. Market Research

### The Accuracy Gap

Research consistently shows the context-to-accuracy relationship:

| Context Level | Accuracy | Who Provides It |
|---------------|----------|----------------|
| Bare schemas only | 10-31% | Databases |
| Technical metadata | 40-50% | Data catalogs |
| Business definitions | 75-80% | Semantic layers |
| **Full context graph** | **94-99%** | **Nobody captures this** |

**Source:** Promethium/Moveworks research (2026), Fluree GraphRAG benchmarks

### Why Current Tools Fail

- **NL→SQL tools** (Julius AI, etc.): Solve query generation, not context capture. Accuracy plateaus at 80% because business context is missing.
- **BI Copilots** (Power BI, Looker): Inherit metric inconsistency from legacy BI. No context capture.
- **ThoughtSpot**: Answers questions you ask. Doesn't proactively surface insights.
- **ChatGPT for data**: No persistent connections, no governance, no enterprise context layer.

### The 80% Problem

The AI analytics industry has spent years building better query engines. The other **80%** (business context) is unsolved:

- Metric definitions (what "revenue" means — bookings vs. recognized vs. net?)
- Fiscal calendars and business rules
- "It depends" logic for edge cases
- Tribal knowledge in analyst heads
- Data source authoritative mappings

**Result:** 95% of AI BI pilots fail to deliver ROI. Even the best tools plateau at 80% accuracy.

### Market Validation

- **Foundation Capital** called context graphs "AI's trillion-dollar opportunity" (December 2025)
- **Gartner** predicts 50%+ of AI agent systems will leverage context graphs by 2028
- **Knowledge Graph market** projected to reach $5.47B by 2033

---

## 2. The Problem Space

### The Five Levels of Context

Context isn't monolithic — it stacks in layers:

| Level | Context Type | Who Has It Today |
|-------|--------------|------------------|
| 1 | Technical metadata (schema, column types) | Databases, catalogs |
| 2 | Relationship context (joins, foreign keys) | Partially in data models |
| 3 | Business definitions (metrics, KPI formulas) | Some BI tools, dbt |
| 4 | Semantic logic (fiscal calendars, rules) | Locked in BI tools |
| 5 | **Tribal knowledge & memory** | **Nobody systematically** |

**Most tools solve Level 1-3.** Level 5 (tribal knowledge + cross-session memory + proactive investigation) is completely unsolved.

### Unsolved Technical Problems

| Problem | Why It's Hard | State |
|---------|--------------|-------|
| Zero-effort context capture | Requires instrumenting use itself so corrections become rules | 🔴 Unsolved |
| Cross-session memory | Session-based tools exist; persistent cross-session doesn't | 🔴 Unsolved |
| Proactive investigation | Needs continuous monitoring + anomaly detection + trust framework | 🔴 Unsolved |
| Schema evolution | Must auto-adapt to new columns without manual rebuilds | 🟡 Partially solved |
| Explainable reasoning | Multi-level provenance from business logic to SQL execution | 🟡 Partially solved |

---

## 3. Competitive Landscape

### Direct Competitors (AI Analytics Chat)

| Competitor | Strength | Weakness (Why They Don't Solve the Core Problem) |
|------------|----------|-------------------------------------------------|
| **Julius AI** | Strong NL→SQL | Generic query layer; no context capture |
| **Power BI Copilot** | Microsoft integration | Inherits BI metric inconsistency |
| **ThoughtSpot** | Excellent query tool | Reactive only; no proactive insights |
| **Metabase AI** | Accessible to non-techs | Limited sophistication |
| **Hex** | Analyst workspace | Requires someone to build analyses |
| **Deepnote** | Collaborative notebooks | Not for ops teams |

### Context Graph Players

| Player | Focus | Gap |
|--------|-------|-----|
| **Promethium** | Federated queries + context graph | Ingestion-focused, not capture-focused |
| **Atlan** | Data governance + context layer | Governance, not tribal knowledge capture |
| **Graphlit** | Operational context for agents | Developer-focused, not business analytics |
| **Cognee** ($7.5M seed) | AI memory for agents | Early stage, not analytics-specific |
| **TrustGraph** | Open-source context graph | Technical tool, not a product |

### Why They Don't Solve It

None capture context **automatically as a byproduct of use**. Every solution requires manual documentation, which:
- Is expensive
- Is inconsistent
- Never stays current
- Creates cold-start problem (need users for context, need context to attract users)

---

## 4. Technical Architecture

### Service Overview

The system is divided into 10 independent services across 5 domains:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURE MAP                                │
│                                                                     │
│  INGESTION DOMAIN              CONTEXT DOMAIN         EXECUTION     │
│  ───────────────              ──────────────         ────────────   │
│                                                                     │
│  1. Context Ingestion  ──▶  3. Context Graph     5. Query        │
│     Service                   Store (Core)          Understanding  │
│                                                                     │
│  2. Feedback Capture    ──▶  4. Context Assembly   6. Query      │
│     Service                   Service               Execution      │
│                                                                     │
│                           ────────────────────                    │
│                                                                     │
│                    INTELLIGENCE DOMAIN                             │
│                                                                     │
│  7. User Memory           8. Schema Discovery    9. Validation &   │
│     Service                 Service              Enrichment            │
│                                                                     │
│                           ────────────────────                    │
│                                                                     │
│                    DELIVERY DOMAIN                                 │
│                                                                     │
│                    10. Proactive Insights                          │
│                         Service + Analytics UI                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Service Dependencies

| Service | Input From | Output To | Independent? |
|---------|-----------|-----------|-------------|
| Context Ingestion | External tools | Graph Store | ✅ |
| Feedback Capture | UI events | Graph, Memory | ✅ |
| Context Graph Store | All ingestion | Assembly, Validation | ⬅️ FOUNDATION |
| Query Understanding | User query | Execution, Assembly | ✅ |
| Context Assembly | Graph + Query | Execution | ⚠️ |
| Query Execution | Query Plan | Validation, Insights | ✅ |
| User Memory | Feedback | Assembly, Understanding | ✅ |
| Schema Discovery | Data sources | Validation | ✅ |
| Validation | Execution + Discovery | Graph Store | ⚠️ |
| Proactive Insights | Execution + Memory | UI | ✅ |

### Build Phases

#### Phase 1: Foundation (Weeks 1-6)
- **Team A:** Context Graph Store (Neo4j/FalkorDB)
- **Team B:** Context Ingestion Service
- **Output:** Populated graph with ingested context

#### Phase 2: Core Loop (Weeks 4-10)
- **Team C:** Query Understanding + Context Assembly
- **Team D:** Query Execution Service
- **Team E:** Feedback Capture Service
- **Output:** End-to-end query pipeline

#### Phase 3: Intelligence (Weeks 8-14)
- **Team F:** User Memory Service
- **Team G:** Schema Discovery Service
- **Team H:** Context Validation & Enrichment Service
- **Output:** Self-improving system

#### Phase 4: Delivery (Weeks 10-16)
- **Team I:** Proactive Insights Service
- **Team J:** Analytics UI + API Gateway
- **Output:** Production user experience

---

## 5. Build Order

### Parallelization Strategy

**7 out of 10 services can start immediately.** The only hard dependency is Context Graph Store.

**Recommended parallel teams (8 teams total):**

1. **Team A:** Context Graph Store — Infrastructure foundation
2. **Team B:** Context Ingestion Service — Populates graph
3. **Team C:** Query Understanding + Context Assembly — Query pipeline
4. **Team D:** Query Execution Service — Data execution
5. **Team E:** Feedback Capture + User Memory — Learning loop
6. **Team F:** Schema Discovery + Validation — Quality
7. **Team G:** Proactive Insights — Intelligence
8. **Team H:** Analytics UI + API Gateway — Frontend

### Interface Contracts (Critical)

Before any team starts, define:

1. **Event schemas** for message queue (Kafka topics)
2. **REST API schemas** for synchronous calls
3. **Data schemas** for shared models
4. **Contract tests** — automated interface verification

**Rule:** Interface changes must be backward-compatible for 2 sprints.

---

## 6. Risks & Mitigation

### Risk 1: Cold-Start Problem
**Risk:** Need users for context, need context to attract users.
**Mitigation:** 
- Start with small, high-intent user group
- Pre-seed context from public sources (dbt docs, industry metrics)
- Make first users' answers visibly better to prove value

### Risk 2: Model Commoditization
**Risk:** LLMs get better at zero-shot, reducing urgency of context.
**Mitigation:**
- Business context lives in organizations, not models
- Context capture from organizational usage is defensible moat
- Models improve; organizational context compounds

### Risk 3: Competition from Incumbents
**Risk:** Google, Microsoft, Palantir move into context layers.
**Mitigation:**
- Focus on capture problem they're ignoring
- Build faster in niche (mid-market analytics)
- Acquire or be acquired is a valid exit

### Risk 4: Data Governance Sensitivity
**Risk:** Enterprises paranoid about where context lives.
**Mitigation:**
- Offer on-premise or encrypted deployment
- Clear data residency controls
- SOC 2 Type II + HIPAA compliance path

### Risk 5: Accuracy Claims
**Risk:** 94-99% accuracy is research benchmark, not production guarantee.
**Mitigation:**
- Measure accuracy in production from day one
- Publish real numbers, not aspirational ones
- Start with narrow domains where context is highest quality

---

## Summary

**The bet:** Build the first analytics tool where context capture is automatic, not manual. Every tool in the market (Julius AI, Power BI Copilot, ThoughtSpot) fails in production because they don't solve the 80% problem. Their accuracy plateaus at 80%. We can reach 94-99% by solving contexts Levels 4-5.

**The moat:** Compounding organizational context — more users, more corrections, more query patterns → smarter context that competitors cannot replicate.

**The metrics:**
- First milestone: 80% accuracy on single-source queries
- Second milestone: 90% accuracy on federated queries with ingest
- Third milestone: 95%+ accuracy with feedback loop + memory

---

## Next Steps

1. **Define interface contracts** — API schemas, event schemas, shared models
2. **Select graph database** — Neo4j (mature) vs. TigerGraph (scale) vs. FalkorDB (speed)
3. **Select LLM provider** — GPT-4o (cost/quality balance) vs. Claude Sonnet (long context)
4. **Build Phase 1 services** — Graph Store + Ingestion in parallel
5. **Validate with users** — A/B test against Julius AI on narrow query set

---

*Documentation generated from market research, competitive analysis, and architecture design sessions.*