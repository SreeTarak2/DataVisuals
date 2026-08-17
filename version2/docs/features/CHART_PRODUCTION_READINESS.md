# Chart System — Production Readiness Roadmap

> **Status:** Living document · Last updated: 2026-07-31
> **Companion doc:** [`CHART_SYSTEM.md`](./CHART_SYSTEM.md) covers *what we have, gaps, and what was done*. This doc covers **what it takes to be production-ready**, the *current system's tradeoffs*, and the *solutions* to them.
> **How to use:** Each tradeoff is marked with severity 🔴/🟡/🟢 and the file where it lives. The implementation plan at the end is the ordered backlog.

---

## 1. Current Architecture (30-second recap)

```
AI Designer → blueprint (components[] with config only, no data) → MongoDB
        ↓
Dashboard page renders blueprint chart components via DashboardComponent
        ↓
useBulkChartHydration → POST /api/ai/{dataset_id}/hydrate-charts  (ONE request)
        ↓  parallel server-side render; manual per-chart retry-chart remains as fallback
chart_render_service.render_chart(df, config)  → traces (Plotly format)
        ↓  LTTB downsampling + metadata.sampling + semantic auto-layout + annotations
        ↓
Frontend: plotlyToECharts.js → ECharts option → EChartsRenderer (canvas)
        ↓
useUrlDashboardState ⇄ crossFilter/drillDownStack in URL (?filter=…&drill=…)
```

---

## 2. Verified Tradeoffs of the Current System

These were verified against the code, not guessed. Each has a concrete solution in §3.

| # | Tradeoff | Severity | Where |
|---|---|---|---|
| 1 | **Chart hydration = N requests per chart.** ~~Every config-only chart fires its own `retry-chart` POST on first load.~~ **✅ Resolved** (2026-07-31): bulk `POST /hydrate-charts` + `useBulkChartHydration` render the whole grid in one request (dataset loaded once). Per-chart `retry-chart` remains only as the manual Retry button. | 🔴 → ✅ | `backend/api/ai/routes.py` (`/hydrate-charts`), `frontend/src/pages/Dashboard/hooks/useBulkChartHydration.js` |
| 2 | **Silent truncation.** The retry-chart endpoint defaults to `max_rows=10000`; `/api/charts/render` defaults to `limit=10000` (schema allows up to 100K) and one internal path (`chart_render_service.py:788`) loads with **no cap at all**. The UI has no idea a chart is showing *a slice*, not the whole story. A 100K-row time series renders the first 10K rows — wrong tail, silent. **🟡 Partially addressed** (2026-07-31): LTTB traces carry `_sampled` and the UI now shows a "1K of 12K pts" honesty badge — but the dataset-load row cap (`max_rows=10000`) is still not surfaced against `metadata.total_rows`. | 🔴 | `backend/api/ai/routes.py`, `backend/api/charts/routes.py`, `backend/services/charts/chart_render_service.py` |
| 3 | **Downsampling is inconsistent and not shape-preserving.** ~~`hydrate.py` caps multi_line at 1000 pts and line at evenly-spaced points.~~ Scatter/heatmap still cap at 500 via `sample(n=500, seed=42)`. **🟡 Partially addressed** (2026-07-31): a real LTTB algorithm (`_lttb_downsample`) now drives line / multi_line / stacked_area / grouped multi-line; scatter + heatmap migration is still open. The old `quis_graph.py` "LTTB" was step-sampling, so a shared util was implemented fresh in `hydrate.py`. | 🟡 | `backend/services/charts/hydrate.py`, `backend/agents/quis/quis_graph.py` |
| 4 | **`chart_data` persists inside the MongoDB dashboard blueprint.** A 10K-point chart's traces live in the dashboard doc. Multi-MB blueprints bloat Mongo, slow every dashboard read, and make concurrent writes (e.g., chat adding components) risky. | 🟡 | `backend/api/ai/routes.py` (`db.dashboards.update_one` with full blueprint) |
| 5 | **Blueprint persistence matching is fragile.** `retry-chart` matches components by `id` → `title` → config signature. `normalizeDashboardConfig` only generates a smart title when one is **missing** (`c.type === 'chart' && !c.title`), and backend components always carry titles — so divergence mainly bites chat-driven / legacy config-only components, where persistence silently skips (rendering still works via direct response). | 🟢 | `backend/api/ai/routes.py`, `frontend/src/utils/dashboardUtils.js` |
| 6 | **Cross-filter is session-only.** ~~`dashboardActionStore` is in-memory Zustand. Refresh → filter gone.~~ **✅ Resolved** (2026-07-31): `useUrlDashboardState` persists `crossFilter` + `drillDownStack` to encoded, validated, per-dataset URL params (`?filter=…&drill=…`, `replace: true`). Note: encoding ≠ encryption — see hook docs + §4 Phase 3 for the PII-safe view-ID upgrade. | 🟡 → ✅ | `frontend/src/store/dashboardActionStore.js`, `frontend/src/pages/Dashboard/hooks/useUrlDashboardState.js` |
| 7 | **Single giant `plotlyToECharts.js` converter.** One ~900-line file handles all 28 chart types. Elegant, but hard to test per-type, review, or extend without risk. The pre-existing dispatcher test failures hint at this fragility. | 🟡 | `frontend/src/utils/plotlyToECharts.js` |
| 8 | **Canvas charts = no accessibility.** ECharts renders to `<canvas>`. No screen-reader path, no keyboard navigation, no data-table fallback. High legal/enterprise risk (ADA, EU A11y Act). | 🟡 | `frontend/src/components/features/charts/renderers/EChartsRenderer.jsx` |
| 9 | **No rendered-traces cache.** `ChartConfigCache` caches chart *configs* per dataset, but `retry-chart` re-renders traces from scratch on every call unless the blueprint already has `chart_data`. Identical configs re-run aggregation + trace building repeatedly. (KPIs cache via `dashboard_cache_service`; rendered chart traces don't.) | 🟡 | `backend/services/cache/__init__.py`, `backend/services/cache/dashboard_cache_service.py` |
| 10 | **Hydration retries are unbounded-ish.** Each chart has `autoRetryAttemptedRef` (one attempt), but there's no global dedupe/backoff across the grid — a backend hiccup means N simultaneous retries per chart across users. | 🟢 | `frontend/src/components/DashboardComponent.jsx` |
| 11 | **No `is_estimated` flag on charts.** KPIs already carry `downsampled`/`is_estimated` metadata; charts silently render downsampled data with no "estimate" badge. **🟡 Partially addressed** (2026-07-31): `metadata.sampling` = `{shown, original_count, method}` now surfaces downsampling and drives the honesty badge; a full `status: estimated` taxonomy remains on the Phase 2 backlog (consistent error taxonomy). | 🟢 | `backend/services/ai/kpi_types.py` (KPI pattern exists), charts lack the equivalent |
| 12 | **Chart traces ignore column-level privacy flags.** A privacy layer exists (`privacyAPI`), but rendered traces don't check it — PII columns could leak into chart tooltips. | 🟡 | `frontend/src/services/api.js` (`privacyAPI`), chart render path |
| 13 | **Tooltip/label content flows unescaped into ECharts.** Chart titles, axis labels, and category names come from data — a hostile dataset could inject HTML into tooltip markup. | 🟢 | `frontend/src/utils/plotlyToECharts.js` (tooltip builder) |
| 14 | **Tests only cover semantic types + overlay.** `test_semantic_types.py` (28 tests) and overlay tests exist; there are **no golden/contract tests for the other 27 chart types** and no E2E browser flow for chart rendering. | 🟡 | `backend/services/tests/`, `frontend/src/components/features/charts/renderers/__tests__/` |

---

## 3. Solutions by Viewpoint

### A. Performance & Scale — the "billions of rows" story

| Solution | Fixes | Effort |
|---|---|---|
| **Bulk hydrate endpoint** — ✅ **Done** (2026-07-31). `POST /api/ai/{dataset_id}/hydrate-charts` loads the dataset once, renders all config-only charts in parallel (`asyncio.gather`), persists successes to the blueprint in a single write, and returns `{hydrated, total, results: [{index, id, title, success, chart_data, updated_config, error}]}`. Frontend `useBulkChartHydration` waits once instead of N times. | #1 | ✅ |
| **Server-side LTTB downsampling** — ✅ **Done for line/area/stacked types** (2026-07-31). Real LTTB (`_lttb_downsample` / `_lttb_downsample_df`) in `hydrate.py`; `quis_graph.py`'s version was step-sampling so a shared util was implemented fresh. ⬜ **Remaining:** migrate scatter/heatmap (`sample(n=500)`) to LTTB for consistency. | #2, #3 | ✅ (partial) |
| **Honest truncation metadata** — ✅ **Done** (2026-07-31) as `metadata.sampling = {shown, original_count, method}` aggregated from trace `_sampled` hints in `render_chart`; DashboardComponent renders a "1K of 12K pts" badge (tooltip shows full numbers). ⬜ **Remaining:** surface the dataset-load row cap against `metadata.total_rows`. | #2, #11 | ✅ (partial) |
| **Rendered-chart cache** — new `ChartRenderCache` keyed by `(dataset_id, config_hash, data_version)`, reusing/extending the storage pattern of the existing `ChartConfigCache` (`services/cache/__init__.py`). `retry-chart` + `hydrate-charts` check it first. Invalidate on dataset re-upload/reprocess. | #9, #4 | 3–4 hrs |
| **ECharts large-data mode** — set `progressive`, `progressiveThreshold`, and `large` series options when `shown_points > threshold`. | #2 | 30 min |

### B. Reliability & Correctness

| Solution | Fixes | Effort |
|---|---|---|
| **Move `chart_data` out of the blueprint** — store rendered charts in a `chart_cache` collection keyed by `(dataset_id, config_hash)`; the blueprint stores only the key. Shrinks dashboard docs, enables cache reuse. | #4 | 3–4 hrs |
| **Global hydration dedupe + backoff** — module-level in-flight map keyed by `(datasetId, title)`, exponential backoff, max 2 attempts per chart per session. | #10 | 1 hr |
| **Version-aware cache invalidation** — bump `data_version` on reprocess; all chart caches keyed on it. | #4, #9 | 1 hr |
| **Consistent error taxonomy** — chart responses carry `status: ok | empty | truncated | estimated | failed`; the UI renders the matching state (empty state, estimate badge, retry panel). | #11 | 2 hrs |
| **Stable component IDs** — the AI designer assigns deterministic `id` to each component so blueprint persistence matching never depends on titles. | #5 | 1–2 hrs |

### C. Product / UX Parity (vs Power BI / Hex)

| Solution | Fixes | Effort |
|---|---|---|
| **URL-persistent filters** — ✅ **Done** (2026-07-31) via `useUrlDashboardState`: `URLSearchParams` encoding (`replace: true`), read-side validation (length/depth caps, string-only), per-dataset scoping, and a crafted-URL consistency guard. Encoding is not encryption — the PII-safe upgrade is the **Bookmarks UI / shared views** row in this section (§3.C) + Phase 3. | #6 | ✅ |
| **100% stacked bar** — one chart type + strategy + prompt rule, following the existing `stacked_bar` pattern. | gap | small |
| **Slicer panel** — category chips + date range feeding the existing `crossFilter` store. | gap | medium |
| **Bookmarks UI** — backend `layout-snapshots` API exists; re-add restore UI in `dashboardActionStore`. | gap | medium |
| **Hierarchy drill-down** — auto Year→Quarter→Month from date columns; breadcrumbs already exist. | gap | medium |
| **Page tooltips** — rich hover panels (ECharts `tooltip.formatter` returning HTML cards). | gap | medium |
| **KPI cross-filter** — when `crossFilter` is active, KPIs re-compute/re-fetch for the filtered slice. | gap | medium |
| **Small multiples** — real facet grids; adapters currently map `facet`/`small_multiples` to plain line/scatter. | gap | hard |

### D. Accessibility

| Solution | Fixes | Effort |
|---|---|---|
| **"View as table" fallback** per chart — reuse `DataPreviewTable` with the chart's underlying rows; toggle in the card header. | #8 | 2–3 hrs |
| **ARIA + keyboard** — `aria-label` per chart ("Bar chart: Revenue by Region"), keyboard-focusable canvas with arrow-key navigation (ECharts has `aria.enabled` and `zr` keyboard support). | #8 | 1–2 hrs |
| **Colorblind-safe palette** — `semantic_types` auto-layout selects a colorblind-safe categorical palette (Okabe-Ito) by default. | #8 | 1 hr |

### E. Testing & Quality

| Solution | Fixes | Effort |
|---|---|---|
| **Golden tests for all 28 chart types** — `hydrate.py` output (traces structure) asserted per type; the `test_semantic_types.py` pattern extended to `test_chart_render.py`. | #14 | 4–5 hrs |
| **Frontend snapshot tests** — Plotly traces → ECharts option per type (`dispatcher.test.jsx` extension). Also fix the 2 pre-existing `backgroundColor` failures while in there. | #7, #14 | 3 hrs |
| **E2E browser flow** — one `browser-use` script: upload → dashboard renders charts → click bar → cross-filter dims → reload → hydration from blueprint. | #14 | 2 hrs |

### F. Security & Governance

| Solution | Fixes | Effort |
|---|---|---|
| **Tooltip/label escaping** — sanitize strings flowing into ECharts `tooltip.formatter` HTML (escape `<`, `>`, `&`); the `prompt_sanitizer` patterns apply client-side too. | #13 | 1 hr |
| **Privacy-aware traces** — chart render path filters columns flagged in the privacy layer before building traces; KPI/chart tooltips never expose PII. | #12 | 2–3 hrs |
| **Rate-limit audit** — `retry-chart`/`hydrate-charts` on `RateLimits.AI_DASHBOARD` is correct; ensure `hydrate-charts` can't be abused to trigger N renders per request (cap charts-per-request). | — | 30 min |

---

## 4. Prioritized Implementation Plan

> Ordered by **user-visible correctness → scale safety → parity → hardening**. Each phase is independently shippable.

### Phase 1 — Fix what's silently wrong 🔴
1. ✅ LTTB downsampling + "shown of total" honesty badge (#2, #3, #11) — `hydrate.py` LTTB + `metadata.sampling` + DashboardComponent badge (scatter/heatmap still on `sample()`, row-cap surfacing still open)
2. ✅ Bulk hydrate endpoint, one request for the whole grid (#1) — `POST /hydrate-charts` + `useBulkChartHydration`
3. ✅ URL-persistent cross-filter (#6) — `useUrlDashboardState` (encoded, validated, per-dataset)
4. ⬜ Stable component IDs (#5) — **next up**

### Phase 2 — Scale safety 🟡
5. Rendered-chart response cache (#9)
6. `chart_data` out of the blueprint → `chart_cache` collection (#4)
7. Hydration dedupe + backoff (#10)

### Phase 3 — Parity & delight 🟡
8. 100% stacked bar
9. Slicer panel
10. Bookmarks UI
11. KPI cross-filter

### Phase 4 — Hardening 🟢
12. Golden tests for all 28 chart types + frontend snapshot tests + E2E flow (#14)
13. A11y: table fallback + ARIA + colorblind palette (#8)
14. Tooltip escaping + privacy-aware traces (#12, #13)

---

## 5. Decision Log

| Date | Decision |
|---|---|
| 2026-07-31 | Cross-filtering re-enabled (see `CHART_SYSTEM.md` §2.1). This roadmap captures the remaining work to reach production readiness. |
| 2026-07-31 | Phase order agreed: correctness → scale → parity → hardening. First execution target: **Phase 1** (LTTB + honesty badge, bulk hydrate, URL filters). |
| 2026-07-31 | **Phase 1 items 1–3 shipped & reviewed** — LTTB downsampling + `metadata.sampling` honesty badge (`hydrate.py`, `chart_render_service.py`, `DashboardComponent.jsx`), bulk `hydrate-charts` endpoint + `useBulkChartHydration`, and `useUrlDashboardState` URL-persistent cross-filter (security-reviewed: encoding ≠ encryption, read-side validation, per-dataset scoping). Remaining Phase 1: stable component IDs (#5). |
