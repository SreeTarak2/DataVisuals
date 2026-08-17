/**
 * useUrlDashboardState
 * --------------------
 * Persists the dashboard cross-filter + drill-down state in the URL so a page
 * reload (or copy/paste of the URL) restores the exact view.
 *
 * SECURITY NOTES (documented because this was an explicit design decision):
 * - Values are persisted via `URLSearchParams`, which handles proper
 *   percent-encoding for `&`, `=`, `#`, spaces, and unicode — the URL is
 *   always valid and unbreakable. This is ENCODING, not encryption: a cross-
 *   filter value like a customer name will appear in browser history, server
 *   logs (if ever sent as a backend param), and Referer headers. Encoding is
 *   intentionally NOT used to hide sensitive data — see the read-side guards.
 * - Read-side validation (defense-in-depth): only string values are accepted,
 *   lengths are capped (filter ≤ 300 chars, drill ≤ 10 levels, labels ≤ 200),
 *   and malformed drill JSON is silently ignored. React's escaping prevents
 *   any XSS when the value renders in the UI.
 * - Tampering is low-risk here: cross-filter is purely client-side (dim effect
 *   + PivotTable row filter), so a forged param can only dim charts to nothing.
 * - Dataset scoping: switching datasets clears the filter/drill so one
 *   dataset's view never leaks into another's.
 *
 * For PII-sensitive deployments the upgrade path is opaque view IDs
 * (?view=<token> stored server-side) — flagged in CHART_PRODUCTION_READINESS.md.
 */

import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import useDashboardActionStore from '../../../store/dashboardActionStore';

const MAX_FILTER_LENGTH = 300;
const MAX_DRILL_DEPTH = 10;
const MAX_LABEL_LENGTH = 200;

export const useUrlDashboardState = (selectedDataset) => {
  const datasetId = selectedDataset?.id || selectedDataset?._id || null;
  const [searchParams, setSearchParams] = useSearchParams();
  const prevDatasetRef = useRef(null);
  const isRestoringRef = useRef(false);

  // ── URL → store (restore on first load, clear on dataset switch) ──
  useEffect(() => {
    if (!datasetId) return;
    const prev = prevDatasetRef.current;
    prevDatasetRef.current = datasetId;

    const store = useDashboardActionStore.getState();

    // Switched datasets: the old dataset's filter/drill must not leak across.
    if (prev && prev !== datasetId) {
      isRestoringRef.current = true;
      store.clearCrossFilter();
      store.clearDrillDown();
      setSearchParams({}, { replace: true });
      isRestoringRef.current = false;
      return;
    }

    // First load: restore from URL if present.
    const filter = searchParams.get('filter');
    const drillRaw = searchParams.get('drill');
    if (!filter && !drillRaw) return;

    isRestoringRef.current = true;
    let restoredFilters = [];

    // ── Restore filter context — multi-select + multi-field ──
    // Accepts the new [{ field, value }] array, the legacy single
    // { field, value } object, and the legacy plain-string value.
    if (typeof filter === 'string' && filter.length > 0 && filter.length <= MAX_FILTER_LENGTH) {
      try {
        const parsed = JSON.parse(filter);
        if (Array.isArray(parsed)) {
          restoredFilters = parsed
            .filter((p) => p && typeof p?.value === 'string' && p.value.length > 0)
            .map((p) => ({
              field: typeof p.field === 'string' ? p.field.slice(0, MAX_LABEL_LENGTH) : null,
              value: p.value.slice(0, MAX_FILTER_LENGTH),
            }));
        } else if (
          parsed &&
          typeof parsed === 'object' &&
          typeof parsed.value === 'string' &&
          parsed.value.length > 0
        ) {
          restoredFilters = [{
            field: typeof parsed.field === 'string' ? parsed.field.slice(0, MAX_LABEL_LENGTH) : null,
            value: parsed.value.slice(0, MAX_FILTER_LENGTH),
          }];
        }
      } catch {
        // Not JSON — legacy plain-string filter value (handled below).
      }
      if (restoredFilters.length === 0 && filter.length > 0) {
        restoredFilters = [{ field: null, value: filter.slice(0, MAX_FILTER_LENGTH) }];
      }
      store.setFilters(restoredFilters);
    }

    if (drillRaw) {
      try {
        const parsed = JSON.parse(drillRaw);
        if (Array.isArray(parsed)) {
          const valid = parsed
            .slice(0, MAX_DRILL_DEPTH)
            .map((level) => ({
              label:
                typeof level?.label === 'string'
                  ? level.label.slice(0, MAX_LABEL_LENGTH)
                  : '',
              values: Array.isArray(level?.values)
                ? level.values.slice(0, MAX_DRILL_DEPTH).map((v) => String(v).slice(0, MAX_FILTER_LENGTH))
                : (typeof level?.filterValue === 'string' ? [level.filterValue] : []),
              filterValue:
                typeof level?.filterValue === 'string'
                  ? level.filterValue.slice(0, MAX_FILTER_LENGTH)
                  : null,
              field:
                typeof level?.field === 'string'
                  ? level.field.slice(0, MAX_LABEL_LENGTH)
                  : null,
              chartTitle:
                typeof level?.chartTitle === 'string'
                  ? level.chartTitle.slice(0, MAX_LABEL_LENGTH)
                  : 'Data',
            }))
            .filter((level) => level.label);
          // Consistency guard against hand-crafted URLs: if the drill stack's
          // last level's field has NO matching value in the restored filter
          // context, drop the stack (the filter badge is the source of truth).
          const lastLevel = valid[valid.length - 1];
          if (lastLevel?.field) {
            const hasMatch = restoredFilters.some(
              (f) => (f.field || null) === lastLevel.field && lastLevel.values.includes(f.value)
            );
            if (!hasMatch) {
              store.clearDrillDown();
            } else {
              store.restoreDrillDownStack(valid);
            }
          } else if (lastLevel?.filterValue && restoredFilters.length > 0) {
            if (lastLevel.filterValue !== restoredFilters[0].value) {
              store.clearDrillDown();
            } else {
              store.restoreDrillDownStack(valid);
            }
          } else {
            store.restoreDrillDownStack(valid);
          }
        }
      } catch {
        // Malformed drill payload — ignore, never crash the dashboard.
      }
    }
    isRestoringRef.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  // ── Store → URL (write encoded params with replace:true, no history spam) ──
  useEffect(() => {
    if (!datasetId) return;

    const unsub = useDashboardActionStore.subscribe((state) => {
      if (isRestoringRef.current) return;

      const { crossFilters, drillDownStack } = state;
      const params = new URLSearchParams();
      if (Array.isArray(crossFilters) && crossFilters.length > 0) {
        // Persist the whole multi-select / multi-field context so a reload
        // restores the exact filter (legacy readers still parse the array).
        params.set(
          'filter',
          JSON.stringify(
            crossFilters.map((f) => ({
              field: f.field || null,
              value: String(f.value).slice(0, MAX_FILTER_LENGTH),
            }))
          )
        );
      }
      if (Array.isArray(drillDownStack) && drillDownStack.length > 0) {
        params.set('drill', JSON.stringify(drillDownStack.slice(0, MAX_DRILL_DEPTH)));
      }

      // Avoid churn: skip when the URL is already identical.
      if (params.toString() === searchParams.toString()) return;
      setSearchParams(params, { replace: true });
    });

    return unsub;
  }, [datasetId, setSearchParams, searchParams]);

  return null;
};

export default useUrlDashboardState;
