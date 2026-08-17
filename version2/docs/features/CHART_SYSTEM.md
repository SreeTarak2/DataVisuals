# Chart System — Complete Overview

> **Status:** Living document · Last updated: 2026-07-31
> **Scope:** Everything related to how DataSage renders, formats, and interacts with charts — what we have, what's missing, and what has been built.
> **Companion:** For the production-readiness roadmap, verified tradeoffs, and prioritized fixes, see [`CHART_PRODUCTION_READINESS.md`](./CHART_PRODUCTION_READINESS.md).

---

## 1. What We Have

### 1.1 Chart Types

The backend prompt + validator recognizes **28 chart types**. The frontend renders them all through a **Plotly → ECharts conversion pipeline** (single unified renderer).

| Family | Chart Types |
|---|---|
| **Comparison** | `bar`, `grouped_bar`, `stacked_bar`, `multi_line`, `pictorial_bar` |
| **Trend** | `line`, `area`, `stacked_area`, `dual_axis`, `combo` |
| **Composition** | `pie`, `donut`, `treemap`, `sunburst`, `sankey`, `theme_river` |
| **Distribution** | `histogram`, `box_plot`, `violin`, `scatter`, `effect_scatter`, `bubble` |
| **Relationship** | `scatter`, `heatmap`, `parallel`, `graph` |
| **Specialized** | `map`, `radar`, `funnel`, `lines`, `tree`, `facet`, `small_multiples` |

**Where they're declared:**
- `backend/prompts/chart.py` — AI prompt mandates chart-type selection rules (group_by, cardinality, part-of-whole → stacked, etc.)
- `backend/core/output_validator.py` — whitelists exact chart-type strings
- `backend/services/charts/chart_recommender.py` — rule-based recommendation engine
- `frontend/src/utils/plotlyToECharts.js` — the Plotly → ECharts converter
- `frontend/src/adapters/EChartsAdapter.js` / `PlotlyAdapter.js` — per-type option builders

### 1.2 Rendering Pipeline

```
AI Designer / Chat intent  →  chart_config {chart_type, columns, x, y, group_by}
        ↓
chart_render_service.render_chart(df, config)   [backend]
        ↓  hydrate.py → traces (Plotly format)
        ↓  semantic auto-layout (see §2.2)
        ↓
POST /api/charts/render   →  {traces, layout, metadata}
        ↓
Frontend ChartRenderer (ECharts-only dispatcher)
        ↓  plotlyToECharts.js converts traces → ECharts option
        ↓  EChartsRenderer renders (dataZoom, brush, shared hover)
```

- **Dashboard flow:** AI Designer writes a *blueprint* (`components[]`) to MongoDB. Chart components carry only `config` (no data). On render, `DashboardComponent` auto-hydrates each chart via `POST /api/ai/{dataset_id}/retry-chart`, then persists the `chart_data` back into the blueprint so it survives reloads.

### 1.3 Chart Data & Formatting

| Layer | What it does |
|---|---|
| **Multi-series engine** | `hydrate.py` builds overlay/facet/dual-axis/combo/grouped/stacked strategies with pattern detection |
| **Semantic types** (`services/charts/semantic_types.py`) | 16 semantic types inferred from dtype + name + sample values: currency, percentage, ratio, temperature, duration, date, datetime, year_month, rank, score, quantity, identifier, dimension, boolean, number, unknown |
| **Auto-layout** (`apply_auto_layout`) | Flint-inspired presentation pass: bar charts pinned to zero baseline, rotated labels for 20+ categories, axis titles from column names, per-type tick formats (`$1.2M`, `45.0%`, `1.2s`) |
| **Statistical overlays** (`chart_render_service`) | Backend computes trend lines, reference lines, mean/median lines, confidence bands; `PlotlyAdapter` renders them as layout shapes/annotations |
| **Semantic axis hints** | `_axis_metadata` → ECharts axis labels, tooltips, and titles (years stay `2024`, never `2K`) |
| **KPI / insight formatting** | Confidence scores, delta %, sparklines on `MetricCard`; `ChartInsightsCard` per-chart AI insights |

### 1.4 Interactions (Enabled)

| Interaction | How it works |
|---|---|
| **Cross-filtering** ✅ *(re-enabled 2026-07-31)* | Click a bar → `DashboardComponent` sets `crossFilter` in the global `dashboardActionStore` → all charts dim non-matching bars (`applyDimEffect`) → section header shows a "Filtering: X" badge with clear button |
| **Brush-select cross-filter** ✅ | ECharts `brush` toolbox (rect/polygon/keep/clear) on axis charts → `brushSelected` event → `chart-brush` window event → same filter store |
| **Drill-down breadcrumbs** ✅ | Double-click a bar pushes a level onto `drillDownStack`; breadcrumbs allow popping back to root |
| **Shared hover / tooltips** ✅ | All charts join the `datasage-dashboard` echarts group → axis pointer + tooltip sync across charts |
| **Data zoom** ✅ | Scroll/inside zoom + slider for exploration |
| **AI Explain** ✅ | Per-chart "AI Explain" button → `POST /api/ai/{id}/explain-chart` |
| **Playground config wells** ✅ | X / Y / Group-By / Aggregation / Number-Format pickers (`CardVerticalConfig`) |

### 1.5 Architecture Files

| Path | Purpose |
|---|---|
| `backend/services/charts/semantic_types.py` | Semantic type inference + `format_spec_for` + `apply_auto_layout` |
| `backend/services/charts/chart_render_service.py` | Render orchestration; statistical annotations; multi-series + semantic passes |
| `backend/services/charts/hydrate.py` | Trace builders per chart type (incl. grouped/stacked) |
| `backend/services/charts/chart_insights_service.py` | Per-chart AI insight/explanation generation |
| `backend/api/charts/routes.py` | `POST /render`, `POST /render-preview`, `GET /recommendations` |
| `backend/api/ai/routes.py` | `POST /{dataset_id}/retry-chart` (chart hydration) |
| `frontend/src/utils/plotlyToECharts.js` | Plotly → ECharts converter + `applyDimEffect` + `buildValueFormatter` |
| `frontend/src/components/DashboardComponent.jsx` | Renders a dashboard chart component; owns cross-filter + drill-down logic |
| `frontend/src/pages/Dashboard/Dashboard.jsx` | Page-level chart grid (bento layout) + cross-filter header badge |
| `frontend/src/store/dashboardActionStore.js` | Global `crossFilter` / `drillDownStack` state |

---

## 2. What Was Recently Done

### 2.1 Cross-Filtering Re-Enabled (2026-07-31)

**Problem:** Cross-filtering was fully implemented in `DashboardComponent` (brush events, click-to-filter, drill-down breadcrumbs, dim effect) but the dashboard page removed the entire chart grid during the "KPI-first refactor" — so charts never rendered and the feature was dead code. The `retry-chart` backend endpoint that hydrates chart data was also commented out.

**Changes:**
1. **Backend** — Re-enabled `POST /api/ai/{dataset_id}/retry-chart` in `backend/api/ai/routes.py`. It renders a component's `chart_data` from its `config` via `chart_render_service`, persists it back into the MongoDB dashboard blueprint (survives reloads), and returns `{success, chart_data, updated_config}`. Dataset load is capped at `max_rows=10000` (configurable) to avoid pulling billions of rows.
2. **Frontend** — Re-enabled the chart grid in `pages/Dashboard/Dashboard.jsx`:
   - Restored the **bento layout engine** (`SPAN_CLASSES` + `createBentoLayout`) for visually varied asymmetric grids.
   - Renders `aiDashboardConfig.components` filtered to `type === 'chart'` through `DashboardComponent`.
   - Destructured `crossFilter`/`setCrossFilter` from the action store (was explicitly commented out as "disabled").
   - Added a **section-header active filter badge** ("Filtering: X" with clear ✕) — the single cross-filter indicator.
3. **Frontend** — Removed the redundant per-card filter chip from `DashboardComponent` (one indicator is enough), removed dead code (`colorOffset`, `computedAnnotations`, unused lucide imports, unused `crossFilterActive`, unused `chartIntelligence` prop).

**Result:** Click any bar → every other chart on the dashboard dims to that selection; the header shows the active filter; brush-drag also works on axis charts; double-click drills down with breadcrumbs.

### 2.2 Flint-Inspired Semantic Types + Auto-Layout (earlier)

- Added `services/charts/semantic_types.py` — 16 semantic types, 3-tier inference (dtype → value → name), with underscore-normalized keyword matching (`total_revenue` → "total revenue").
- `apply_auto_layout()` applies presentation rules: zero baseline for bar-like charts, rotated dense-axis labels, axis titles, per-type number formatting.
- Wired into **both** single-series (`render_chart`) and multi-series (`render_multi_series`) paths, with strategy→chart_type mapping so stacked/grouped bars get the zero baseline.
- Frontend `buildValueFormatter` converts backend `_axis_metadata` hints into real ECharts axis labels + tooltips + titles.
- 28 unit tests in `backend/services/tests/test_semantic_types.py`.

### 2.3 Statistical Annotation Bridge (earlier)

`chart_config` now supports statistical annotations (trend lines, reference lines, confidence bands) computed server-side; both renderers draw them as visible overlays.

---

## 3. What We DON'T Have (Gaps vs Power BI / Hex)

Ranked by effort vs. impact. This is the honest gap list.

### 🔴 High-impact, low-effort (not built yet)

| Gap | Notes |
|---|---|
| **100% stacked bar** | We have `stacked_bar` but no normalized-to-100% variant. Small addition (one strategy + prompt rule). |
| **Slicer panel** | Only a `DateRangeBar` exists on the Charts page. No category slicer chips that feed the *existing* crossFilter store. |
| **Bookmarks UI** | Backend API exists (`/api/datasets/{id}/layout-snapshots/`) and Settings can export a snapshot, but the restore UI was removed (`dashboardActionStore` notes "no UI"). |

### 🟡 Medium effort

| Gap | Notes |
|---|---|
| **True hierarchy drill-down** (Year → Quarter → Month) | We have click-driven drill-down (via breadcrumbs) but no *hierarchy tree* navigation. Date columns could auto-create Year→Quarter→Month levels. |
| **Page/rich tooltips** (custom hover panels) | Only native ECharts tooltips. Power BI's rich tooltip pages aren't present. |

### 🔵 Harder / strategic

| Gap | Notes |
|---|---|
| **Small multiples (real grids)** | `facet` / `small_multiples` are declared as chart types but adapters map them to plain line/scatter — they don't render true facet grids yet. |
| **Cross-filter on KPIs** | KPIs don't react to the active filter (they could show filtered values). |
| **Filter persistence / shared dashboards** | Filters are per-session in the Zustand store; no URL state or shareable view. |
| **Managed vector DB / very large scale** | Out of chart scope — see `docs/architecture/HANDLING_BILLIONS_OF_ROWS.md`. |

---

## 4. Design Principles

1. **One renderer, many types.** Everything flows through Plotly-format traces → single ECharts converter. No per-type component forks in the dashboard grid.
2. **AI chooses, math formats.** The LLM picks chart types & columns; deterministic services handle number formatting, baselines, and layout so numbers are never wrong.
3. **Data never re-fetched on reload.** Hydrated `chart_data` persists in the dashboard blueprint.

> **Note:** `retry-chart` persistence matches blueprint components by `id` → `title` → config signature. The frontend's `normalizeDashboardConfig` can generate smart titles for unnamed components, so a normalized title may differ from the stored blueprint title and persistence silently skips (rendering still works — `chart_data` returns directly in the response).
4. **One filter source of truth.** `dashboardActionStore.crossFilter` is the single cross-chart filter; every chart reads it reactively.

---

## 5. Quick Reference — Supporting API

| Endpoint | Purpose |
|---|---|
| `POST /api/charts/render` | Render chart from dataset config (primary) |
| `POST /api/charts/render-preview` | Quick preview without AI insights |
| `GET /api/charts/recommendations` | AI chart-type recommendations |
| `POST /api/ai/{id}/retry-chart` | Hydrate/retry a dashboard chart component |
| `POST /api/charts/explain` | Per-chart AI explanation |
| `GET /api/dashboard/{id}/config` | Full AI dashboard blueprint |
| `POST /api/datasets/{id}/layout-snapshots/` | Save/restore dashboard layouts (UI pending) |
