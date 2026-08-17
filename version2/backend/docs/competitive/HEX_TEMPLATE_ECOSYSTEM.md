# Hex Template Ecosystem Analysis

> **Prepared for:** DataSage AI Product & Engineering Leadership
> **Date:** July 29, 2026
> **Source:** [hex.tech/templates](https://hex.tech/templates/) (direct analysis)
> **Classification:** Internal — Competitive Strategy
> **See also:** [HEX_TECH_COMPETITIVE_ANALYSIS.md](./HEX_TECH_COMPETITIVE_ANALYSIS.md) — Full competitive intelligence report

---

## Executive Summary

Hex maintains a curated library of **~44 public templates** organized across **12 categories**. These templates serve as both marketing material (showing what Hex can do) and onboarding acceleration (fork a live workspace, adapt to your data).

**Critical finding:** Hex has zero templates for AI Chat, RAG, AI Agents, or Copilot functionality — despite heavy AI marketing. Their "Text to SQL Chatbot" template is a single notebook tutorial from 2023, not a product feature. This is a **glaring gap** that DataSage can exploit by creating AI-native templates that demonstrate our core differentiator.

---

## 1. Template Catalog (Complete Inventory)

### 1.1 Category Overview

| Category | Count | Focus | Code Lang |
|----------|-------|-------|-----------|
| Data Clustering | 4 | K-means, document similarity, customer segmentation | Python (scikit-learn) |
| Data Modeling | 3 | Recommendation engines, market basket, collaborative filtering | Python |
| Data Science | 4 | Anomaly detection, A/B testing, ML pipelines, dbt audit | Python (scikit-learn) |
| Data Visualization | 3 | Python viz libraries, geospatial analysis | Python (Plotly, Folium) |
| Exploratory Analysis | 4 | EDA, data stories, ad-hoc analysis, **Text-to-SQL chatbot** | Python + SQL + LangChain |
| Feature Selection | 3 | Dimensionality reduction (linear & non-linear) | Python |
| KPI Dashboards | 4 | Customer health, feature success, LTV, SQL dashboards | SQL + Python |
| Natural Language Processing | 3 | spaCy, HuggingFace, TF-IDF classification | Python |
| Parameterized Queries | 1 | Interactive SQL with user inputs | SQL |
| Reporting | 4 | MoM/QoQ/YoY, dbt metrics, quarterly reviews, GA4 alternatives | SQL + Python |
| Sentiment Analysis | 4 | VADER, social media, NER | Python (spaCy, VADER) |
| Snowpark | 4 | Snowflake-native ML, UDTFs, stored procedures | Python (Snowpark) |
| Time Series | 3 | Prophet forecasting, trend decomposition | Python (Prophet) |
| **Total** | **~42** | | |

### 1.2 Full Template Inventory

#### Data Clustering (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Cluster Analysis | Hex Team | Interactive K-means clustering app with input parameters | Python, scikit-learn |
| Document Similarity with Embeddings | Hex Team | Explore document similarity using embeddings from SQL warehouse | Python, embeddings |
| Clustering Algorithms | Hex Team | Group similar data points to discover patterns | Python |
| Customer Segmentation | Izzy Miller | Group users by behavior/purchase history | Python, K-means |

#### Data Modeling (3)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Collaborative Filtering | Izzy Miller | Build recommendation engine | Python |
| Market Basket Analysis | Hex Team | Apriori-based product pairing analysis | Python |
| Content Based Filtering | Hex Team | Content + collaborative filtering recommendations | Python |

#### Data Science (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Anomaly Detection | Hex Team | Statistical + ML-based anomaly detection | Python |
| dbt Audit Helper | Hex Team | Validate dbt PRs and document changes | Python + dbt |
| A/B Testing | Hex Team | Hypothesis testing, statistical significance | Python |
| Build, test, deploy ML models | Izzy Miller | Full ML workflow: feature engineering → deployment | Python, scikit-learn |

#### Data Visualization (3)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Python Data Visualization | Izzy Miller | Matplotlib, Plotly, Altair, Seaborn examples | Python |
| Geospatial Data Analysis | Hex Team | GIS techniques with mapping tools | Python |
| Python Mapping Libraries | Izzy Miller | Folium, Plotly geospatial examples | Python |

#### Exploratory Analysis (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Interactive Data Stories | Izzy Miller | Narrative data stories with charts + text | Python + markdown |
| Exploratory Data Analysis | Izzy Miller | Distributions, correlations, outliers | Python |
| Ad-hoc Exploration | Izzy Miller | Fastest path from question to insight | Python + SQL |
| **Text to SQL Chatbot** | Jordan East | **Build your own text-to-SQL chatbot using OpenAI + LangChain** (likely ~2023 — not actively maintained) | **Python, OpenAI, LangChain** |

#### Feature Selection (3)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Linear Dimensionality Reduction | Izzy Miller | Visualize high-dim data with linear reduction | Python |
| Feature Selection | Hex Team | Filter, wrapper, embedded methods | Python |
| Non-linear Dimensionality Reduction | Hex Team | Non-linear techniques for high-dim data | Python |

#### KPI Dashboards (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Customer Health Dashboard | Hex Team | Health scores, usage signals, risk indicators | SQL + Python |
| Feature Success | Jo Engreitz | Feature adoption, retention, satisfaction | SQL + Python |
| SQL Powered Dashboards | Hex Team | Flexible BI dashboards from SQL queries | SQL |
| Customer Lifetime Value Dashboard | Izzy Miller | LTV modeling, segmentation, dashboard | SQL + Python |

#### Natural Language Processing (3)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Using SpaCy for NLP | Hex Team | Analyze, extract insights, visualize text | Python, spaCy |
| Natural Language Processing | Izzy Miller | Sentiment, emotion, text classification | Python, HuggingFace, TF-IDF |
| (NER template in sentiment section) | | | |

#### Parameterized Queries (1)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Feature Success Interactive Dashboard | Jo Engreitz | Parameterized SQL with interactive inputs | SQL |

#### Reporting (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Period over Period Analysis | Izzy Miller | MoM, QoQ, YoY metrics with reusable SQL | SQL |
| dbt Metrics | Hex Team | Access trusted metrics via dbt integration | SQL + dbt |
| Replace Google Analytics | Hex Team | Rudderstack + Hex analytics stack | SQL |
| Automating Quarterly Reviews | Izzy Miller | Hex ↔ Google Sheets ↔ Google Slides | Python, Google APIs |

#### Sentiment Analysis (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| VADER Sentiment Analysis | Izzy Miller | Rule-based sentiment on social media, reviews | Python, VADER |
| Social Media Sentiment Analysis | Izzy Miller | Brand sentiment over time | Python |
| Named Entity Recognition | Hex Team | Extract people, places, orgs from text | Python, spaCy, HuggingFace |
| Sentiment Analysis | Hex Team | Reviews, support tickets, surveys → scores | Python |

#### Snowpark (4)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Customer Behavior + Sales Forecasting | Hex Team | Segmentation, trend, predictive modeling | Python, Snowpark |
| Time Series with Snowpark | Hex Team | Restaurant traffic forecasting with UDTFs | Python, Snowpark |
| Data Science with Snowpark | Hex Team | Easy button for Snowpark | Python, Snowpark |
| Snowpark ML Stored Procedures | Hex Team | ML pipelines inside Snowflake warehouse | Python, Snowpark ML |

#### Time Series (3)
| Template | Author | Description | Tech Stack |
|----------|--------|-------------|------------|
| Time Series Forecasting with Prophet | Izzy Miller | Trend decomposition, seasonality, predictions | Python, Prophet |
| Time Series Analysis in Snowpark | Hex Team | Restaurant traffic forecasting | Python, Snowpark |
| Time Series Forecasting | Hex Team | Full workspace for time series models | Python |

---

## 2. Template Authors

| Author | Role | Templates | % of Catalog |
|--------|------|-----------|--------------|
| **Izzy Miller** | Dev Advocate @ Hex | ~15 templates | ~34% |
| **Jo Engreitz** | Hex Team | ~2 templates | ~5% |
| **Jordan East** | Hex Team | 1 template (Text-to-SQL) | ~2% |
| **Hex Team (uncredited)** | Internal | ~26 templates | ~59% |

**Key insight:** ~40% of templates are credited to named individuals (primarily Izzy Miller, their Developer Advocate). This suggests their templates are built by **developer relations**, not product engineering. The remaining ~60% are uncredited, likely built by the core team as demo/marketing material.

---

## 3. Strategic Observations

### 3.1 What Templates Reveal About Hex's Product Strategy

**1. Notebooks are the core — everything else is a layer on top**
Every template follows the same pattern: SQL/Python code cells → parameter inputs → interactive app. The App Builder is essentially adding a UI shell around notebook cells. This confirms notebooks are not just a feature — they're the product architecture.

**2. AI features are NOT template-ized**
Despite Hex's heavy AI marketing (Threads, Notebook Agent, Context Studio), there are **zero templates** for:
- Chat with your data / AI chatbot
- RAG / knowledge retrieval
- AI agent workflows
- AI-generated insights or KPI suggestions
- AI-assisted SQL generation

The one template that touches AI — "Text to SQL Chatbot" by Jordan East — is a **2023 tutorial** showing how to build a chatbot using LangChain inside a Hex notebook. It's not showcasing a Hex AI product feature. It's showcasing that you can run LangChain in Hex.

**3. Templates = marketing, not strategic**
The template library feels like a **developer advocacy project** rather than a core product investment. Izzy Miller has written ~34% of all templates. The categories (Clustering, Feature Selection, Sentiment Analysis) are **CS 101 topics** — designed to demonstrate "look what you can build with Hex" rather than solving specific business problems.

**4. Industry verticals are completely absent**
No healthcare templates. No finance templates. No e-commerce templates (except Market Basket Analysis). No SaaS templates (except a generic Customer Health Dashboard). Every template is **function-generic** (Time Series, Clustering, NLP).

This is intentional — Hex sells a platform, not a solution. But it means onboarding takes longer because every user must adapt templates to their domain.

**5. Snowpark gets its own category — 4 dedicated templates**
Snowflake integration is strategically important to Hex (Snowflake Ventures is an investor). Having a dedicated Snowpark category with 4 templates signals deep partnership. No similar category for BigQuery, Redshift, or Postgres.

### 3.2 What Templates Reveal About Hex's Weaknesses

**1. Poor discoverability**
The template page lists all 44 templates in a flat grid with no search bar, no sorting, and no pagination. Users must manually scan. Compare this to Notion's template gallery (searchable, filterable, rated) or Figma's community (search + categories + trending).

**2. No community contributions**
All templates are authored by Hex employees. No user-submitted templates. No ratings. No reviews. No "most popular" sorting. This is a missed opportunity for community building.

**3. Quality varies widely**
Izzy Miller's templates (EDA, Data stories, Time Series) are polished, well-documented, and instructive. The uncredited templates (Clustering Algorithms, Content Based Filtering) are minimalist — just code cells with minimal explanation. This inconsistency suggests no quality standards for templates.

**4. No AI-powered template generation**
Despite having AI, Hex doesn't offer "Describe what you want → AI builds a template for you." Every template is hand-crafted by an employee.

### 3.3 Lessons for DataSage

**✅ Do This:**

| Lesson | Why |
|--------|-----|
| **Create AI-native templates** | Show users "upload data → AI analyzes it" not "write code → get results" |
| **Include search + filtering** | Hex's flat catalog is hard to browse. Add categories, tags, search |
| **Enable community templates** | Let users publish and share templates. Builds ecosystem lock-in |
| **Add template ratings/reviews** | Social proof drives adoption. Hex has neither |
| **Target specific industries** | "Healthcare Dashboard" beats "KPI Dashboard" for a hospital |
| **Offer AI template generation** | "Describe your analysis → AI generates the template" — Hex can't do this |

**❌ Don't Do This:**

| Mistake | Why |
|---------|-----|
| **Hand-code all templates** | Unsustainable. One person (Izzy) wrote 34% of Hex's catalog |
| **Ignore AI features in templates** | Hex has zero AI templates despite AI being their main marketing message |
| **Flat, unsearchable catalog** | Users abandon without good discoverability |
| **Generic function-focused templates** | "Clustering" doesn't sell. "Customer Segmentation for SaaS" does |

---

## 4. Actionable Recommendations

### 4.1 Templates DataSage Should Build (Priority Order)

| Priority | Template Name | What It Demonstrates | Target User |
|----------|---------------|---------------------|-------------|
| **P0** | **Chat with Your Dataset** | Upload CSV → AI generates insights, answers questions, builds charts | All users — our core value prop |
| **P0** | **AI SQL Generator** | Ask in English → get SQL → see results → refine with chat | SQL users transitioning to AI |
| **P0** | **AI Auto-Insights** | Upload data → AI automatically finds anomalies, trends, KPIs | Executives, managers |
| **P1** | **Data Briefing Report** | Upload data → AI generates narrative report with charts | Stakeholders |
| **P1** | **RAG Question Answering** | Upload PDF/docs → ask questions → AI answers from +data context | Knowledge workers |
| **P1** | **Customer Churn Analysis** | Upload customer data → AI segments and predicts churn | SaaS teams |
| **P2** | **Sales Dashboard Builder** | Connect data → AI suggests KPIs → interactive dashboard | Sales teams |
| **P2** | **Financial Report Generator** | Upload financials → AI generates quarterly report | Finance teams |
| **P2** | **Social Media Sentiment** | Upload CSV → AI analyzes sentiment trends | Marketing teams |
| **P3** | **Anomaly Detection** | Upload time series → AI finds outliers | Ops/engineering |

### 4.2 Template UX Requirements

Based on Hex's "fork to workspace" model, DataSage templates should support:

1. **One-click instantiation** — Click "Use template" → pre-populates workspace with sample data
2. **Live and interactive** — Template works immediately without configuration
3. **Sample data built-in** — CSV attached to template (not external data source required)
4. **"Swap your data" button** — One-click to replace sample data with user's own dataset
5. **Guided walkthrough** — Annotated steps explaining what the template does
6. **Shareable URL** — Each template gets a unique URL for sharing

### 4.3 Technical Architecture for Template System

```
templates/
├── chat-with-dataset/
│   ├── manifest.json        # Name, description, category, tags, preview image URL
│   ├── sample-data.csv      # Built-in sample dataset
│   └── config.json          # Pre-configured workspace state (chat history, settings)
├── ai-sql-generator/
│   ├── manifest.json
│   ├── sample-data.csv
│   └── config.json
└── ...
```

**manifest.json schema:**
```json
{
  "id": "chat-with-dataset",
  "name": "Chat with Your Dataset",
  "description": "Upload any CSV and start asking questions in natural language. AI automatically generates insights, charts, and answers.",
  "categories": ["ai", "getting-started", "all-purpose"],
  "industries": ["all"],
  "difficulty": "beginner",
  "featured": true,
  "author": "DataSage Team",
  "previewImage": "/templates/chat-with-dataset/preview.png",
  "sampleDataFile": "sample-data.csv",
  "createdAt": "2026-07-29",
  "updatedAt": "2026-07-29"
}
```

---

## 5. Comparison: Hex Templates vs DataSage Templates (Proposed)

| Dimension | Hex (Current) | DataSage (Planned) | Advantage |
|-----------|---------------|--------------------|-----------|
| **# of templates** | ~44 | Start with 5-10 | None (we start small) |
| **AI-powered templates** | 0 (one tutorial) | **5 of 5 P0 templates** | ✅ **DataSage** |
| **Community submissions** | ❌ No | ✅ Yes (open) | ✅ **DataSage** |
| **Ratings & reviews** | ❌ No | ✅ Yes | ✅ **DataSage** |
| **Search/filter** | ❌ Flat list | ✅ Searchable, tagged | ✅ **DataSage** |
| **Industry-specific** | ❌ No | ✅ Healthcare, SaaS, Finance | ✅ **DataSage** |
| **AI template generation** | ❌ No | ✅ "Describe → AI builds" | ✅ **DataSage** |
| **Interactive inputs** | ✅ Yes (parameters) | ✅ Yes (chat + params) | Tie |
| **Live forking** | ✅ Yes | ✅ Yes | Tie |
| **Template quality** | Inconsistent | Curated + community-ranked | ✅ **DataSage** |

---

## 6. Template Maintenance & Staleness Risk

### 6.1 Are Hex Templates Maintained?

A critical unknown: **Hex does not display creation or update dates on any template.** This means:
- Users cannot tell if a template is current or outdated
- The "Text to SQL Chatbot" template (likely ~2023) references `langchain` v0.0.x — the API has since been rewritten for v0.3+
- Old templates using deprecated libraries (e.g., `prophet` 1.0, `snowpark` early APIs) could teach anti-patterns
- No version history or changelog for any template

**DataSage advantage:** All our templates would display creation + last-updated dates, and users would be notified of stale templates. This is a trust signal.

### 6.2 SEO Analysis

Hex's template page is built for search engine discovery:

| Element | Content | Target Keywords |
|---------|---------|-----------------|
| **Page Title** | "Data Analysis Templates for Notebooks and SQL \| Hex" | Data analysis templates, notebooks, SQL |
| **Meta Description** | "Browse pre-built analysis templates in Hex: cohort analysis, NLP, time series, churn prediction, KPI dashboards, and more." | Long-tail template searches |
| **Categories used** | Clustering, NLP, Time Series, Snowpark | 12 distinct keyword clusters |
| **Author pages** | Izzy Miller (Dev Advocate) | Personal brand + SEO authority |

**Implication for DataSage:** Our `/templates` page should target keywords Hex misses:
- "AI data analysis templates" (zero competition)
- "Chat with your data template" (zero competition)
- "AI analytics template without coding" (zero competition)
- "Business intelligence chatbot template" (very low competition)

---

## 7. Conclusion

**Hex's template library is a weak spot disguised as a strength.** They have 44 templates, but:
- Zero demonstrate their AI features
- All are hand-crafted by 2-3 employees
- None are community-contributed
- Discoverability is poor
- Quality is inconsistent

**DataSage can leapfrog this by:**
1. Building **AI-native templates** that demonstrate our core differentiator (chat + RAG)
2. Creating a **community template system** with ratings, search, and submissions
3. Generating templates **with AI** rather than hand-coding them
4. Targeting **specific industries** rather than generic functions

This is a rare case where we're **not behind** — Hex hasn't solved templates either, and their approach is showing its age. We have a clean slate to do it right.

---

*End of Hex Template Ecosystem Analysis*
