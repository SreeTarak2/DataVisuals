"""
SurprisingPatternsEngine — Discovers hidden, non-obvious patterns in data
=======================================================================
Tier 2 & 3 KPI insights that users would not find by glancing at dashboards.

Engines (all deterministic, zero LLM cost):
  1. Correlation mining — find metric pairs that should move together but don't
  2. Ratio anomalies — compute derived ratios that tell hidden stories
  3. Simpson's paradox — aggregate trend hides opposing segment trends
  4. Concentration risk — one segment dominates dangerously
  5. Segment decomposition — find which segment drives all the change
  6. Ratio drift — semantically linked metrics diverging over time

Each engine returns SurprisingInsight objects that get rendered as insight cards
alongside standard KPI cards in the dashboard.

Production-hardened with:
  - Time-aware splitting (sorted by time_col when available)
  - Correlation pair cap (max 50 pairs to avoid O(N²) blowup)
  - Deduplication across engines (prevents similar insights on same metrics)
  - Configurable thresholds (all magic numbers are class constants)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from .intelligent_kpi_generator import (
    ColumnProfile,
    ColumnRole,
    _fmt_val,
)

logger = logging.getLogger(__name__)


# ── Configurable Defaults ─────────────────────────────────────────────────────

# These can be overridden by passing them to the constructor.
# Stored as module-level constants so they serve as self-documenting defaults.
_DEFAULT_MIN_ROWS = 30
_DEFAULT_MIN_SEGMENT_ROWS = 15
_DEFAULT_CORRELATION_THRESHOLD = 0.6
_DEFAULT_HIGH_CORRELATION_THRESHOLD = 0.85
_DEFAULT_FDR_ALPHA = 0.05  # Benjamini-Hochberg FDR significance level
_DEFAULT_DIVERGENCE_MIN_CHANGE_PCT = 5.0
_DEFAULT_MIN_RATIO_CHANGE_PCT = 10.0
_DEFAULT_MIN_AGGREGATE_CHANGE_PCT = 3.0
_DEFAULT_MIN_SEGMENT_CHANGE_PCT = 2.0
_DEFAULT_CONCENTRATION_THRESHOLD_PCT = 50.0
_DEFAULT_SEGMENT_CONTRIBUTION_THRESHOLD_PCT = 70.0
_DEFAULT_RATIO_DRIFT_MIN_PCT = 15.0
_DEFAULT_SIMPSON_PARADOX_MAX_MEASURES = 5
_DEFAULT_SIMPSON_PARADOX_MAX_DIMS = 4
_DEFAULT_CONCENTRATION_MAX_MEASURES = 6
_DEFAULT_CONCENTRATION_MAX_DIMS = 5
_DEFAULT_SEGMENT_DECOMP_MAX_MEASURES = 5
_DEFAULT_SEGMENT_DECOMP_MAX_DIMS = 4
_DEFAULT_MAX_CORRELATION_PAIRS = 50
_DEFAULT_DEDUP_TITLE_SIMILARITY_THRESHOLD = 0.6


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class SurprisingInsight:
    """One discovered non-obvious pattern, ready to render as an insight card."""

    type: str  # "correlation" | "ratio" | "simpson" | "concentration" | "segment"
    title: str
    description: str
    impact: str = ""
    severity: str = "info"  # "info" | "warning" | "critical"
    metrics: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    category: str = "hidden_pattern"

    def to_card(self) -> Dict[str, Any]:
        """Convert to a card dict consumable by the frontend insight renderer."""
        return {
            "type": "insight",
            "insight_type": self.type,
            "title": self.title,
            "description": self.description,
            "plain_english": self.description,
            "impact": self.impact,
            "severity": self.severity,
            "category": self.category,
            "metrics": self.metrics,
            "evidence": self.evidence,
            "tags": self._tags(),
        }

    def _tags(self) -> List[str]:
        tags = [self.type.replace("_", " ").title()]
        if self.severity == "critical":
            tags.append("High Impact")
        elif self.severity == "warning":
            tags.append("Watch")
        return tags


# ── Benjamini-Hochberg FDR Correction ─────────────────────────────────────────


def _apply_bh_fdr(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """
    Apply Benjamini-Hochberg FDR correction to a list of p-values.

    Args:
        p_values: List of raw p-values from statistical tests.
        alpha: Desired false discovery rate (default 0.05).

    Returns:
        List of booleans, True if the corresponding test is significant after FDR.
    """
    if not p_values:
        return []

    n = len(p_values)
    # Sort p-values ascending, track original indices
    sorted_indices = sorted(range(n), key=lambda i: p_values[i])
    sorted_pvals = [p_values[i] for i in sorted_indices]

    # BH threshold: p_k ≤ (k / n) * alpha
    # Find the largest k where p_(k) ≤ (k / n) * alpha
    max_significant_k = -1
    for k in range(1, n + 1):
        threshold = (k / n) * alpha
        if sorted_pvals[k - 1] <= threshold:
            max_significant_k = k

    # Mark indices up to max_significant_k as significant
    significant = [False] * n
    for i in range(max_significant_k):
        original_idx = sorted_indices[i]
        significant[original_idx] = True

    return significant


# ── Engine ────────────────────────────────────────────────────────────────────


class SurprisingPatternsEngine:
    """Runs all pattern discovery engines and returns ranked, deduplicated insights.

    All thresholds and limits are configurable via constructor kwargs for
    production tuning without code changes.
    """

    def __init__(
        self,
        max_insights: int = 6,
        # ── Configurable thresholds ──────────────────────────────────────
        min_rows: int = _DEFAULT_MIN_ROWS,
        min_segment_rows: int = _DEFAULT_MIN_SEGMENT_ROWS,
        correlation_threshold: float = _DEFAULT_CORRELATION_THRESHOLD,
        high_correlation_threshold: float = _DEFAULT_HIGH_CORRELATION_THRESHOLD,
        fdr_alpha: float = _DEFAULT_FDR_ALPHA,
        divergence_min_change_pct: float = _DEFAULT_DIVERGENCE_MIN_CHANGE_PCT,
        min_ratio_change_pct: float = _DEFAULT_MIN_RATIO_CHANGE_PCT,
        min_aggregate_change_pct: float = _DEFAULT_MIN_AGGREGATE_CHANGE_PCT,
        min_segment_change_pct: float = _DEFAULT_MIN_SEGMENT_CHANGE_PCT,
        concentration_threshold_pct: float = _DEFAULT_CONCENTRATION_THRESHOLD_PCT,
        segment_contribution_threshold_pct: float = _DEFAULT_SEGMENT_CONTRIBUTION_THRESHOLD_PCT,
        ratio_drift_min_pct: float = _DEFAULT_RATIO_DRIFT_MIN_PCT,
        # ── Engine iteration caps ────────────────────────────────────────
        simpson_paradox_max_measures: int = _DEFAULT_SIMPSON_PARADOX_MAX_MEASURES,
        simpson_paradox_max_dims: int = _DEFAULT_SIMPSON_PARADOX_MAX_DIMS,
        concentration_max_measures: int = _DEFAULT_CONCENTRATION_MAX_MEASURES,
        concentration_max_dims: int = _DEFAULT_CONCENTRATION_MAX_DIMS,
        segment_decomp_max_measures: int = _DEFAULT_SEGMENT_DECOMP_MAX_MEASURES,
        segment_decomp_max_dims: int = _DEFAULT_SEGMENT_DECOMP_MAX_DIMS,
        # ── Performance caps ─────────────────────────────────────────────
        max_correlation_pairs: int = _DEFAULT_MAX_CORRELATION_PAIRS,
        # ── Dedup ────────────────────────────────────────────────────────
        dedup_title_similarity_threshold: float = _DEFAULT_DEDUP_TITLE_SIMILARITY_THRESHOLD,
    ):
        self.max_insights = max_insights
        self.min_rows = min_rows
        self.min_segment_rows = min_segment_rows
        self.correlation_threshold = correlation_threshold
        self.high_correlation_threshold = high_correlation_threshold
        self.fdr_alpha = fdr_alpha
        self.divergence_min_change_pct = divergence_min_change_pct
        self.min_ratio_change_pct = min_ratio_change_pct
        self.min_aggregate_change_pct = min_aggregate_change_pct
        self.min_segment_change_pct = min_segment_change_pct
        self.concentration_threshold_pct = concentration_threshold_pct
        self.segment_contribution_threshold_pct = segment_contribution_threshold_pct
        self.ratio_drift_min_pct = ratio_drift_min_pct
        self.simpson_paradox_max_measures = simpson_paradox_max_measures
        self.simpson_paradox_max_dims = simpson_paradox_max_dims
        self.concentration_max_measures = concentration_max_measures
        self.concentration_max_dims = concentration_max_dims
        self.segment_decomp_max_measures = segment_decomp_max_measures
        self.segment_decomp_max_dims = segment_decomp_max_dims
        self.max_correlation_pairs = max_correlation_pairs
        self.dedup_title_similarity_threshold = dedup_title_similarity_threshold

    # ── Time-aware splitting ────────────────────────────────────────────────

    def _split_periods(
        self, df: pl.DataFrame, time_col: Optional[str] = None
    ) -> Tuple[pl.DataFrame, pl.DataFrame]:
        """Split dataframe into two halves, time-aware when possible.

        When `time_col` is provided and present in the dataframe, sorts by it
        before splitting, ensuring the comparison is truly "earlier vs later"
        rather than "first half of rows vs second half of rows".

        Returns (None, None) when no valid time column is available — all callers
        must handle this by skipping the insight rather than using a row-order split.
        """
        if time_col and time_col in df.columns:
            try:
                sorted_df = df.sort(time_col)
                mid = sorted_df.height // 2
                return sorted_df[:mid], sorted_df[mid:]
            except Exception:
                pass
        # No time column — return None instead of row-based split fallback
        return None, None

    # ── Main entry point ─────────────────────────────────────────────────────

    def discover_all(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """Run all engines and return the most surprising insights."""
        insights: List[SurprisingInsight] = []

        try:
            insights.extend(self._find_correlation_anomalies(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Correlation mining failed: {e}")

        try:
            insights.extend(self._find_ratio_anomalies(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Ratio anomalies failed: {e}")

        try:
            insights.extend(self._find_simpsons_paradox(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Simpson's paradox failed: {e}")

        try:
            insights.extend(self._find_concentration_risks(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Concentration risk failed: {e}")

        try:
            insights.extend(self._find_segment_decomposition(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Segment decomposition failed: {e}")

        try:
            insights.extend(self._find_ratio_drift(df, profiles, time_col))
        except Exception as e:
            logger.debug(f"[SurprisingPatterns] Ratio drift failed: {e}")

        # ── Deduplicate across engines ────────────────────────────────────
        insights = self._deduplicate(insights)

        # Rank: critical > warning > info, then by evidence magnitude
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        insights.sort(
            key=lambda i: (
                severity_order.get(i.severity, 3),
                -abs(i.evidence.get("magnitude", 0)),
            )
        )

        return insights[: self.max_insights]

    # ── Deduplication ────────────────────────────────────────────────────────

    def _deduplicate(self, insights: List[SurprisingInsight]) -> List[SurprisingInsight]:
        """Remove similar insights that refer to the same metrics or have overlapping titles.

        Two insights are considered duplicates if:
          - They share > dedup_title_similarity_threshold word overlap in their title, OR
          - Their `metrics` lists share any common column name

        When a duplicate is found, the one with higher severity (or same severity
        but higher magnitude) is kept.
        """
        if len(insights) < 2:
            return insights

        kept: List[SurprisingInsight] = []
        for insight in insights:
            is_dup = False
            insight_words = set(insight.title.lower().split())
            insight_metrics = set(insight.metrics)

            for i, existing in enumerate(kept):
                existing_words = set(existing.title.lower().split())
                # Title word overlap
                if len(insight_words) > 2 and len(existing_words) > 2:
                    overlap = len(insight_words & existing_words) / min(
                        len(insight_words), len(existing_words)
                    )
                    if overlap > self.dedup_title_similarity_threshold:
                        is_dup = True
                        # Replace if current insight is more severe or has higher magnitude
                        curr_sev = {"critical": 0, "warning": 1, "info": 2}.get(
                            insight.severity, 3
                        )
                        exist_sev = {"critical": 0, "warning": 1, "info": 2}.get(
                            existing.severity, 3
                        )
                        if curr_sev < exist_sev or (
                            curr_sev == exist_sev
                            and insight.evidence.get("magnitude", 0)
                            > existing.evidence.get("magnitude", 0)
                        ):
                            kept[i] = insight
                        break

                # Shared metrics overlap
                if not is_dup and insight_metrics:
                    shared = insight_metrics & set(existing.metrics)
                    if shared:
                        is_dup = True
                        # Same replacement logic as above
                        curr_sev = {"critical": 0, "warning": 1, "info": 2}.get(
                            insight.severity, 3
                        )
                        exist_sev = {"critical": 0, "warning": 1, "info": 2}.get(
                            existing.severity, 3
                        )
                        if curr_sev < exist_sev or (
                            curr_sev == exist_sev
                            and insight.evidence.get("magnitude", 0)
                            > existing.evidence.get("magnitude", 0)
                        ):
                            kept[i] = insight
                        break

            if not is_dup:
                kept.append(insight)

        return kept

    # ── Engine 1: Correlation Anomalies ──────────────────────────────────────

    def _find_correlation_anomalies(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Find metric pairs that are strongly correlated but recently diverged.
        Capped at `max_correlation_pairs` to avoid O(N²) blowup on wide datasets.

        E.g.: "Headcount and Revenue are strongly correlated (r=0.89),
               but this period Revenue grew 15% while Headcount dropped 3%.
               You're doing more with less — or quality is slipping."
        """
        numeric_profiles = [
            p
            for p in profiles
            if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT, ColumnRole.RATE)
            and p.primary_value is not None
            and p.null_pct < 50
        ]

        if len(numeric_profiles) < 2:
            return []

        numeric_cols = [p.name for p in numeric_profiles]
        if len(numeric_cols) < 2:
            return []

        # ── Compute pairwise correlations (fast matrix-based pre-filter) ───
        try:
            corr_df = df.select(numeric_cols).drop_nulls()
            if corr_df.height < self.min_rows:
                return []

            # Step 1: Fast correlation matrix (pandas, vectorized) to find candidate pairs
            corr_matrix = corr_df.to_pandas().corr(method="spearman")

            # Collect all pairs that pass the correlation threshold
            prefilter_pairs: List[Tuple[ColumnProfile, ColumnProfile, float]] = []
            n_cols = len(numeric_profiles)
            for i in range(n_cols):
                for j in range(i + 1, n_cols):
                    p1 = numeric_profiles[i]
                    p2 = numeric_profiles[j]
                    corr_val = corr_matrix.loc[p1.name, p2.name]
                    if corr_val is None or math.isnan(corr_val):
                        continue
                    corr_val = float(corr_val)
                    if abs(corr_val) >= self.correlation_threshold:
                        prefilter_pairs.append((p1, p2, corr_val))

            if not prefilter_pairs:
                return []

            # Sort by absolute correlation descending, take top N×2 for p-value computation
            prefilter_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            # Compute p-values for the top pairs (2× max to leave headroom after FDR)
            max_for_pval = min(len(prefilter_pairs), self.max_correlation_pairs * 2)
            pairs_for_pval = prefilter_pairs[:max_for_pval]

            # Step 2: Compute Spearman p-values only for pre-filtered pairs
            raw_pairs: List[Tuple[ColumnProfile, ColumnProfile, float, float]] = []
            for p1, p2, r_val in pairs_for_pval:
                try:
                    with np.errstate(all="ignore"):
                        _, p_val = spearmanr(
                            corr_df[p1.name].to_numpy(),
                            corr_df[p2.name].to_numpy(),
                        )
                    if math.isnan(p_val):
                        continue
                    p_val = float(p_val)
                    raw_pairs.append((p1, p2, r_val, p_val))
                except Exception:
                    continue

            if not raw_pairs:
                return []

            # ── Benjamini-Hochberg FDR correction ─────────────────────────
            pair_p_values = [p[3] for p in raw_pairs]
            significant = _apply_bh_fdr(pair_p_values, alpha=self.fdr_alpha)

            # Filter: only keep pairs that pass FDR
            fdr_pairs = [
                raw_pairs[i] for i in range(len(raw_pairs)) if significant[i]
            ]

            if not fdr_pairs:
                return []

            # Sort by absolute correlation descending, cap at max
            fdr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            pairs: List[Tuple[ColumnProfile, ColumnProfile, float]] = [
                (p1, p2, r_val) for p1, p2, r_val, _ in fdr_pairs[: self.max_correlation_pairs]
            ]
        except Exception:
            return []

        if not pairs:
            return []

        # ── Time-aware split (skip if no time column) ─────────────────────
        first_half, second_half = self._split_periods(df, time_col)
        if first_half is None:
            return []

        insights: List[SurprisingInsight] = []

        for p1, p2, corr_val in pairs:
            try:
                # Check if they share a business category (semantically related)
                is_same_category = (
                    p1.business_category != "unknown"
                    and p1.business_category == p2.business_category
                )

                # Skip if same category and highly correlated (expected)
                if is_same_category and abs(corr_val) > self.high_correlation_threshold:
                    continue

                # Compute delta for each metric using time-aware halves
                v1_a = _agg_col(first_half, p1.name, p1.aggregation)
                v2_a = _agg_col(second_half, p1.name, p1.aggregation)
                v1_b = _agg_col(first_half, p2.name, p2.aggregation)
                v2_b = _agg_col(second_half, p2.name, p2.aggregation)

                if not v1_a or not v2_a or not v1_b or not v2_b:
                    continue

                delta_a = ((v2_a - v1_a) / abs(v1_a)) * 100 if v1_a != 0 else 0
                delta_b = ((v2_b - v1_b) / abs(v1_b)) * 100 if v1_b != 0 else 0

                # Both must have non-trivial changes
                if abs(delta_a) < self.divergence_min_change_pct and abs(delta_b) < self.divergence_min_change_pct:
                    continue

                # Flag if they MOVED IN OPPOSITE DIRECTIONS despite high correlation
                if (delta_a > 0 and delta_b < 0) or (delta_a < 0 and delta_b > 0):
                    dir_a = "growing" if delta_a > 0 else "declining"
                    dir_b = "growing" if delta_b > 0 else "declining"
                    name_a = _safe_title(p1.name)
                    name_b = _safe_title(p2.name)

                    severity = "warning" if abs(delta_a) > 15 or abs(delta_b) > 15 else "info"

                    insights.append(
                        SurprisingInsight(
                            type="correlation",
                            title=f"{name_a} and {name_b} are diverging",
                            description=(
                                f"{name_a} is {dir_a} ({abs(delta_a):.0f}%) while "
                                f"{name_b} is {dir_b} ({abs(delta_b):.0f}%), despite "
                                f"being strongly correlated (r={corr_val:.2f}). "
                                f"This break from the historical pattern is worth investigating."
                            ),
                            impact=(
                                f"Unexpected divergence — consider reviewing the drivers of {name_a} and {name_b}"
                            ),
                            severity=severity,
                            metrics=[p1.name, p2.name],
                            evidence={
                                "correlation": round(corr_val, 2),
                                "delta_a": round(delta_a, 1),
                                "delta_b": round(delta_b, 1),
                                "magnitude": abs(delta_a - delta_b),
                            },
                        )
                    )

                # Also flag if delta magnitudes are very different
                elif abs(delta_a - delta_b) > 25 and abs(corr_val) > 0.7:
                    meaning_a = "grew" if delta_a > 0 else "shrank"
                    meaning_b = "grew" if delta_b > 0 else "shrank"
                    name_a = _safe_title(p1.name)
                    name_b = _safe_title(p2.name)

                    insights.append(
                        SurprisingInsight(
                            type="correlation",
                            title=f"{name_a} outpaces {name_b}",
                            description=(
                                f"Both {name_a} and {name_b} {'grow' if delta_a > 0 else 'shrink'}, "
                                f"but {name_a} {meaning_a} by {abs(delta_a):.0f}% while "
                                f"{name_b} {meaning_b} by only {abs(delta_b):.0f}%. "
                                f"The gap ({abs(delta_a - delta_b):.0f} percentage points) "
                                f"is unusually large given their historical correlation (r={corr_val:.2f})."
                            ),
                            impact=f"{name_a} is decoupling from {name_b} — find out why",
                            severity="warning" if abs(delta_a - delta_b) > 40 else "info",
                            metrics=[p1.name, p2.name],
                            evidence={
                                "correlation": round(corr_val, 2),
                                "delta_a": round(delta_a, 1),
                                "delta_b": round(delta_b, 1),
                                "magnitude": abs(delta_a - delta_b),
                            },
                        )
                    )

            except Exception:
                continue

        return insights

    # ── Engine 2: Ratio Anomalies ────────────────────────────────────────────

    def _find_ratio_anomalies(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Compute non-obvious ratios that tell hidden stories.
        Uses time-aware splitting.

        E.g.: "Revenue per customer dropped 22% despite total revenue growing 18%.
               This means you're adding low-value customers."
        """
        # Semantic pairs that produce interesting ratios
        ratio_templates = [
            (("revenue", "users", "Revenue per Customer", "currency")),
            (("revenue", "orders", "Average Order Value", "currency")),
            (("revenue", "employees", "Revenue per Employee", "currency")),
            (("cost", "revenue", "Cost Ratio", "percentage")),
            (("cost", "users", "Cost per Customer", "currency")),
            (("profit", "revenue", "Profit Margin", "percentage")),
            (("orders", "visitors", "Conversion Rate", "percentage")),
            (("orders", "users", "Orders per Customer", "number")),
            (("users", "visitors", "Signup Rate", "percentage")),
            (("revenue", "cost", "Revenue per Cost", "number")),
        ]

        # Build a column index: normalized name → actual column name
        col_index: Dict[str, str] = {}
        for p in profiles:
            nl = p.name.lower().replace("_", " ").replace("-", " ")
            col_index[nl] = p.name

        # Time-aware split (skip if no time column)
        first_half, second_half = self._split_periods(df, time_col)
        if first_half is None:
            return []

        insights: List[SurprisingInsight] = []

        for num_pattern, den_pattern, ratio_name, fmt in ratio_templates:
            try:
                num_col = self._fuzzy_match(num_pattern, col_index, profiles)
                den_col = self._fuzzy_match(den_pattern, col_index, profiles)

                if not num_col or not den_col:
                    continue
                if num_col == den_col:
                    continue
                if num_col not in df.columns or den_col not in df.columns:
                    continue

                num_profile = next((p for p in profiles if p.name == num_col), None)
                den_profile = next((p for p in profiles if p.name == den_col), None)
                if not num_profile or not den_profile:
                    continue

                # Compute ratio using time-aware halves
                num_p1 = _agg_col(first_half, num_col, num_profile.aggregation)
                num_p2 = _agg_col(second_half, num_col, num_profile.aggregation)
                den_p1 = _agg_col(first_half, den_col, den_profile.aggregation)
                den_p2 = _agg_col(second_half, den_col, den_profile.aggregation)

                if not all([num_p1, num_p2, den_p1, den_p2]):
                    continue
                if den_p1 == 0 or den_p2 == 0:
                    continue

                ratio1 = num_p1 / den_p1
                ratio2 = num_p2 / den_p2

                if fmt == "percentage":
                    ratio1 *= 100
                    ratio2 *= 100

                if ratio1 == 0:
                    continue

                ratio_delta = ((ratio2 - ratio1) / abs(ratio1)) * 100

                # Must be a meaningful change
                if abs(ratio_delta) < self.min_ratio_change_pct:
                    continue

                num_delta = ((num_p2 - num_p1) / abs(num_p1)) * 100 if num_p1 != 0 else 0
                den_delta = ((den_p2 - den_p1) / abs(den_p1)) * 100 if den_p1 != 0 else 0

                num_name = _safe_title(num_col)
                den_name = _safe_title(den_col)
                ratio_str = _fmt_val(ratio2, fmt)
                direction = "increased" if ratio_delta > 0 else "dropped"

                # THE INSIGHT: ratio moved opposite to one of its components
                if (ratio_delta > 0 and num_delta < 0) or (ratio_delta < 0 and num_delta > 0):
                    verb = "increased" if ratio_delta > 0 else "dropped"
                    description = (
                        f"{ratio_name} {verb} to {ratio_str} ({abs(ratio_delta):.0f}%), "
                        f"{_direction_clause(num_delta, num_name, den_delta, den_name)} "
                        f"This is a non-obvious metric that reveals the net effect of both components."
                    )
                elif (ratio_delta > 0 and den_delta < 0) or (ratio_delta < 0 and den_delta > 0):
                    verb = "increased" if ratio_delta > 0 else "dropped"
                    description = (
                        f"{ratio_name} {verb} to {ratio_str} ({abs(ratio_delta):.0f}%), "
                        f"{_direction_clause(num_delta, num_name, den_delta, den_name)} "
                        f"This efficiency metric tells a different story than either component alone."
                    )
                else:
                    verb = "grew" if ratio_delta > 0 else "shrank"
                    description = (
                        f"{ratio_name} {verb} {abs(ratio_delta):.0f}% to {ratio_str}. "
                        f"{num_name} changed by {abs(num_delta):.0f}% while "
                        f"{den_name} changed by {abs(den_delta):.0f}%. "
                        f"The ratio captures the net effect."
                    )

                severity = (
                    "critical"
                    if abs(ratio_delta) > 30
                    else ("warning" if abs(ratio_delta) > 20 else "info")
                )

                insights.append(
                    SurprisingInsight(
                        type="ratio",
                        title=f"{ratio_name} {direction} {abs(ratio_delta):.0f}%",
                        description=description,
                        impact=f"This ratio combines {num_name} and {den_name} — changes here reveal structural shifts",
                        severity=severity,
                        metrics=[num_col, den_col],
                        evidence={
                            "current_ratio": round(ratio2, 4),
                            "previous_ratio": round(ratio1, 4),
                            "ratio_delta_pct": round(ratio_delta, 1),
                            "numerator_delta_pct": round(num_delta, 1),
                            "denominator_delta_pct": round(den_delta, 1),
                            "magnitude": abs(ratio_delta),
                        },
                    )
                )

            except Exception:
                continue

        return insights

    # ── Engine 3: Simpson's Paradox ──────────────────────────────────────────

    def _find_simpsons_paradox(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Simpson's Paradox: aggregate trend goes one way, but every segment
        goes the opposite way. Uses time-aware splitting.

        E.g.: "Revenue grew 10% overall, but every product category actually
               declined. New categories are masking the drop."
        """
        measures = [
            p
            for p in profiles
            if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT, ColumnRole.RATE)
        ]
        dimensions = [
            p
            for p in profiles
            if p.role == ColumnRole.DIMENSION and 2 <= p.n_unique <= 10
        ]

        if not measures or not dimensions:
            return []

        # Time-aware split (skip if no time column)
        first_half, second_half = self._split_periods(df, time_col)
        if first_half is None:
            return []

        insights: List[SurprisingInsight] = []

        for measure in measures[: self.simpson_paradox_max_measures]:
            for dim in dimensions[: self.simpson_paradox_max_dims]:
                try:
                    metric_col = measure.name
                    dim_col = dim.name

                    if metric_col not in df.columns or dim_col not in df.columns:
                        continue

                    clean = df.drop_nulls(subset=[metric_col, dim_col])
                    if clean.height < 20:
                        continue

                    # Period-specific halves (time-aware re-split on cleaned data)
                    seg_first, seg_second = self._split_periods(clean, time_col)
                    if seg_first is None:
                        continue

                    agg_total_val1 = _agg_col(seg_first, metric_col, measure.aggregation)
                    agg_total_val2 = _agg_col(seg_second, metric_col, measure.aggregation)

                    if not agg_total_val1 or not agg_total_val2 or agg_total_val1 == 0:
                        continue

                    agg_trend = (
                        (agg_total_val2 - agg_total_val1) / abs(agg_total_val1)
                    ) * 100

                    if abs(agg_trend) < self.min_aggregate_change_pct:
                        continue

                    # Per-segment trends
                    segment_vals1 = (
                        seg_first.group_by(dim_col)
                        .agg(pl.col(metric_col).sum().alias("_v1"))
                    )
                    segment_vals2 = (
                        seg_second.group_by(dim_col)
                        .agg(pl.col(metric_col).sum().alias("_v2"))
                    )

                    merged = segment_vals1.join(segment_vals2, on=dim_col, how="inner")

                    # Check if ALL segments move opposite to aggregate
                    all_opposite = True
                    segment_details: List[Dict[str, Any]] = []
                    for row in merged.iter_rows(named=True):
                        s1 = float(row["_v1"])
                        s2 = float(row["_v2"])
                        if s1 == 0:
                            all_opposite = False
                            continue
                        seg_trend = ((s2 - s1) / abs(s1)) * 100
                        if abs(seg_trend) < self.min_segment_change_pct:
                            continue
                        segment_details.append(
                            {
                                "segment": str(row[dim_col]),
                                "trend": round(seg_trend, 1),
                            }
                        )
                        if (seg_trend > 0) == (agg_trend > 0):
                            all_opposite = False

                    if len(segment_details) < 2:
                        continue

                    if all_opposite and len(segment_details) >= 2:
                        agg_dir = "grew" if agg_trend > 0 else "declined"
                        seg_dir = "declined" if agg_trend > 0 else "grew"
                        name = _safe_title(metric_col)

                        seg_names = [s["segment"] for s in segment_details[:3]]
                        seg_str = ", ".join(seg_names)
                        if len(segment_details) > 3:
                            seg_str += f" and {len(segment_details) - 3} more"

                        insights.append(
                            SurprisingInsight(
                                type="simpson",
                                title=f"Hidden reversal: {name}",
                                description=(
                                    f"{name} {agg_dir} {abs(agg_trend):.0f}% overall, "
                                    f"yet every segment ({seg_str}) actually {seg_dir}. "
                                    f"This is a classic Simpson's paradox — the aggregate "
                                    f"number is misleading because segment sizes changed."
                                ),
                                impact=f"The aggregate {_safe_title(metric_col)} trend is misleading — "
                                f"look at individual segment trends instead",
                                severity="critical",
                                metrics=[metric_col, dim_col],
                                evidence={
                                    "aggregate_trend_pct": round(agg_trend, 1),
                                    "segment_trends": segment_details,
                                    "magnitude": abs(agg_trend),
                                },
                            )
                        )

                except Exception:
                    continue

        return insights

    # ── Engine 4: Concentration Risk ─────────────────────────────────────────

    def _find_concentration_risks(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Find when one segment dominates a metric dangerously.
        Uses time-aware splitting for concentration trend detection.

        E.g.: "92% of revenue comes from the Enterprise segment.
               If Enterprise churns, revenue drops 92%."
        """
        measures = [
            p for p in profiles if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT)
        ]
        dimensions = [
            p
            for p in profiles
            if p.role == ColumnRole.DIMENSION and 2 <= p.n_unique <= 15
        ]

        if not measures or not dimensions:
            return []

        # Time-aware split (skip if no time column)
        first_half, second_half = self._split_periods(df, time_col)
        if first_half is None:
            return []

        insights: List[SurprisingInsight] = []

        for measure in measures[: self.concentration_max_measures]:
            for dim in dimensions[: self.concentration_max_dims]:
                try:
                    metric_col = measure.name
                    dim_col = dim.name

                    if metric_col not in df.columns or dim_col not in df.columns:
                        continue

                    clean = df.drop_nulls(subset=[metric_col, dim_col])
                    if clean.height < self.min_segment_rows:
                        continue

                    grouped = (
                        clean.group_by(dim_col)
                        .agg(pl.col(metric_col).sum().alias("_sum"))
                        .sort("_sum", descending=True)
                    )

                    if grouped.height < 2:
                        continue

                    total = float(grouped["_sum"].sum())
                    if total == 0:
                        continue

                    top_row = grouped.head(1)
                    top_segment = str(top_row[dim_col].to_list()[0])
                    top_value = float(top_row["_sum"].to_list()[0])
                    top_pct = (top_value / abs(total)) * 100

                    # Check if concentration changed over time
                    def _segment_concentration(half_df: pl.DataFrame) -> Optional[float]:
                        if half_df.height < 5:
                            return None
                        h_grouped = (
                            half_df.group_by(dim_col)
                            .agg(pl.col(metric_col).sum().alias("_hsum"))
                            .sort("_hsum", descending=True)
                        )
                        h_total = float(h_grouped["_hsum"].sum())
                        if h_total == 0:
                            return None
                        return (
                            float(h_grouped.head(1)["_hsum"].to_list()[0]) / abs(h_total)
                        ) * 100

                    pct_p1 = _segment_concentration(first_half)
                    pct_p2 = _segment_concentration(second_half)

                    name = _safe_title(metric_col)

                    # Flag: if top segment > configured threshold → concentration risk
                    if top_pct > self.concentration_threshold_pct:
                        trend_str = ""
                        if pct_p1 and pct_p2 and abs(pct_p2 - pct_p1) > 5:
                            trend_dir = "increasing" if pct_p2 > pct_p1 else "decreasing"
                            trend_str = f" Concentration is {trend_dir} ({pct_p1:.0f}% → {pct_p2:.0f}%)."

                        severity = (
                            "critical"
                            if top_pct > 80
                            else ("warning" if top_pct > 60 else "info")
                        )

                        insights.append(
                            SurprisingInsight(
                                type="concentration",
                                title=f"{top_segment} dominates {name}",
                                description=(
                                    f"{top_pct:.0f}% of {name} comes from the "
                                    f"'{top_segment}' segment.{trend_str} "
                                    f"With {grouped.height - 1} other segments contributing "
                                    f"the remaining {100 - top_pct:.0f}%, this is a "
                                    f"significant concentration risk."
                                ),
                                impact=f"Losing {top_segment} would mean losing {top_pct:.0f}% of {name} — "
                                f"consider segment diversification",
                                severity=severity,
                                metrics=[metric_col],
                                evidence={
                                    "top_segment": top_segment,
                                    "top_segment_share_pct": round(top_pct, 1),
                                    "segment_count": grouped.height,
                                    "concentration_change_pct": (
                                        round((pct_p2 or top_pct) - (pct_p1 or top_pct), 1)
                                        if pct_p1 and pct_p2
                                        else None
                                    ),
                                    "magnitude": top_pct,
                                },
                            )
                        )

                except Exception:
                    continue

        return insights

    # ── Engine 5: Segment Decomposition ──────────────────────────────────────

    def _find_segment_decomposition(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Decompose metric change into segment contributions.
        Uses time-aware splitting.

        E.g.: "92% of revenue growth came from the Enterprise segment.
               SMB actually shrank. You're staking growth on one segment."
        """
        measures = [
            p for p in profiles if p.role in (ColumnRole.MEASURE, ColumnRole.COUNT)
        ]
        dimensions = [
            p
            for p in profiles
            if p.role == ColumnRole.DIMENSION and 2 <= p.n_unique <= 10
        ]

        if not measures or not dimensions:
            return []

        # Time-aware split (skip if no time column)
        first_half, second_half = self._split_periods(df, time_col)
        if first_half is None:
            return []

        insights: List[SurprisingInsight] = []

        for measure in measures[: self.segment_decomp_max_measures]:
            for dim in dimensions[: self.segment_decomp_max_dims]:
                try:
                    metric_col = measure.name
                    dim_col = dim.name

                    if metric_col not in df.columns or dim_col not in df.columns:
                        continue

                    clean = df.drop_nulls(subset=[metric_col, dim_col])
                    if clean.height < 20:
                        continue

                    total_p1 = _agg_col(first_half, metric_col, measure.aggregation)
                    total_p2 = _agg_col(second_half, metric_col, measure.aggregation)

                    if not total_p1 or not total_p2 or total_p1 == 0:
                        continue

                    total_change = total_p2 - total_p1
                    total_change_pct = (total_change / abs(total_p1)) * 100

                    if abs(total_change_pct) < self.min_aggregate_change_pct:
                        continue

                    # Per-segment change using time-aware halves
                    seg_p1 = (
                        first_half.group_by(dim_col)
                        .agg(pl.col(metric_col).sum().alias("_p1"))
                    )
                    seg_p2 = (
                        second_half.group_by(dim_col)
                        .agg(pl.col(metric_col).sum().alias("_p2"))
                    )

                    merged = seg_p1.join(seg_p2, on=dim_col, how="inner")

                    contributions: List[Dict[str, Any]] = []
                    for row in merged.iter_rows(named=True):
                        s1 = float(row["_p1"])
                        s2 = float(row["_p2"])
                        change = s2 - s1
                        if abs(change) < 1e-6:
                            continue
                        contribution_pct = (
                            (change / abs(total_change)) * 100 if total_change != 0 else 0
                        )
                        contributions.append(
                            {
                                "segment": str(row[dim_col]),
                                "change": round(change, 2),
                                "contribution_pct": round(contribution_pct, 1),
                            }
                        )

                    if len(contributions) < 2:
                        continue

                    contributions.sort(
                        key=lambda c: abs(c["contribution_pct"]), reverse=True
                    )

                    top = contributions[0]
                    if abs(top["contribution_pct"]) > self.segment_contribution_threshold_pct:
                        seg_name = top["segment"]
                        direction = "growth" if top["contribution_pct"] > 0 else "decline"

                        others_moved_opposite = any(
                            (c["contribution_pct"] > 0) != (top["contribution_pct"] > 0)
                            for c in contributions[1:]
                        )

                        agg_dir = "grew" if total_change_pct > 0 else "declined"

                        if others_moved_opposite:
                            description = (
                                f"{_safe_title(metric_col)} {agg_dir} {abs(total_change_pct):.0f}% overall, "
                                f"but {abs(top['contribution_pct']):.0f}% of the "
                                f"{direction} came from '{seg_name}'. "
                                f"Other segments actually moved in the opposite direction, "
                                f"meaning '{seg_name}' is single-handedly carrying "
                                f"the entire {direction} story."
                            )
                        else:
                            description = (
                                f"{abs(top['contribution_pct']):.0f}% of {_safe_title(metric_col)} "
                                f"{direction} came from '{seg_name}'. "
                                f"The remaining {', '.join(c['segment'] for c in contributions[1:4])} "
                                f"contributed just {100 - abs(top['contribution_pct']):.0f}% combined."
                            )

                        severity = (
                            "critical"
                            if abs(top["contribution_pct"]) > 90
                            else "warning"
                        )

                        insights.append(
                            SurprisingInsight(
                                type="segment",
                                title=f"'{seg_name}' drives {abs(top['contribution_pct']):.0f}% of {direction}",
                                description=description,
                                impact=f"Growth is concentrated in one segment — "
                                f"if '{seg_name}' stalls, so does {_safe_title(metric_col)}",
                                severity=severity,
                                metrics=[metric_col, dim_col],
                                evidence={
                                    "top_segment": seg_name,
                                    "top_contribution_pct": round(top["contribution_pct"], 1),
                                    "total_change_pct": round(total_change_pct, 1),
                                    "segment_contributions": contributions,
                                    "magnitude": abs(top["contribution_pct"]),
                                },
                            )
                        )

                except Exception:
                    continue

        return insights

    # ── Engine 6: Ratio Drift ────────────────────────────────────────────────

    def _find_ratio_drift(
        self,
        df: pl.DataFrame,
        profiles: List[ColumnProfile],
        time_col: Optional[str] = None,
    ) -> List[SurprisingInsight]:
        """
        Find semantically linked metric pairs whose relationship is drifting.
        Uses time-aware quarter-based analysis.

        E.g.: "For every $1 of marketing spend, you used to get $5 in revenue.
               Now you get $3. Efficiency is declining."
        """
        linked_pairs = [
            ("cost", "revenue", "Revenue per Cost"),
            ("spend", "sales", "Sales per Spend"),
            ("marketing", "leads", "Leads per Marketing"),
            ("ad spend", "revenue", "ROAS"),
            ("employees", "revenue", "Revenue per Employee"),
            ("customers", "revenue", "Revenue per Customer"),
        ]

        col_index: Dict[str, str] = {}
        for p in profiles:
            nl = p.name.lower().replace("_", " ").replace("-", " ")
            col_index[nl] = p.name

        insights: List[SurprisingInsight] = []

        for indep_pattern, dep_pattern, name in linked_pairs:
            try:
                indep_col = self._fuzzy_match(indep_pattern, col_index, profiles)
                dep_col = self._fuzzy_match(dep_pattern, col_index, profiles)

                if not indep_col or not dep_col or indep_col == dep_col:
                    continue
                if indep_col not in df.columns or dep_col not in df.columns:
                    continue

                clean = df.drop_nulls(subset=[indep_col, dep_col])
                if clean.height < 15:
                    continue

                # Time column is required for ratio drift analysis
                if not time_col or time_col not in clean.columns:
                    continue
                sorted_df = clean.sort(time_col)

                n = sorted_df.height
                quarter_size = max(1, n // 4)

                quarters = [
                    sorted_df[:quarter_size],
                    sorted_df[quarter_size : quarter_size * 2],
                    sorted_df[quarter_size * 2 : quarter_size * 3],
                    sorted_df[quarter_size * 3 :],
                ]

                ratios = []
                for q_df in quarters:
                    if q_df.height < 3:
                        continue
                    indep_sum = float(q_df[indep_col].sum())
                    dep_sum = float(q_df[dep_col].sum())
                    if indep_sum == 0:
                        continue
                    ratios.append(dep_sum / indep_sum)

                if len(ratios) < 2:
                    continue

                first_half_avg = sum(ratios[: len(ratios) // 2]) / (len(ratios) // 2)
                second_half_avg = sum(ratios[len(ratios) // 2 :]) / (
                    len(ratios) - len(ratios) // 2
                )

                if first_half_avg == 0:
                    continue

                drift_pct = (
                    (second_half_avg - first_half_avg) / abs(first_half_avg)
                ) * 100

                if abs(drift_pct) < self.ratio_drift_min_pct:
                    continue

                drift_dir = "increasing" if drift_pct > 0 else "declining"
                indep_name = _safe_title(indep_col)
                dep_name = _safe_title(dep_col)

                insights.append(
                    SurprisingInsight(
                        type="ratio",
                        title=f"{name} is {drift_dir} ({abs(drift_pct):.0f}%)",
                        description=(
                            f"For every unit of {indep_name}, {dep_name} is "
                            f"{drift_dir} by {abs(drift_pct):.0f}%. "
                            f"This means {indep_name} is becoming {'more' if drift_pct > 0 else 'less'} "
                            f"effective at generating {dep_name}. "
                            f"If this trend continues, it will significantly impact overall performance."
                        ),
                        impact=f"{indep_name} efficiency is {drift_dir} — review resource allocation",
                        severity="warning" if abs(drift_pct) > 25 else "info",
                        metrics=[indep_col, dep_col],
                        evidence={
                            "first_half_ratio": round(first_half_avg, 4),
                            "second_half_ratio": round(second_half_avg, 4),
                            "drift_pct": round(drift_pct, 1),
                            "magnitude": abs(drift_pct),
                        },
                    )
                )

            except Exception:
                continue

        return insights

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fuzzy_match(
        pattern: str,
        col_index: Dict[str, str],
        profiles: List[ColumnProfile],
    ) -> Optional[str]:
        """Find the best column match for a semantic pattern."""
        pattern_words = set(pattern.lower().split())

        best_score = 0
        best_col = None

        for nl, actual_col in col_index.items():
            nl_words = set(nl.split())
            overlap = len(pattern_words & nl_words)
            if overlap > best_score:
                best_score = overlap
                best_col = actual_col

        return best_col


# ── Module-Level Helpers ──────────────────────────────────────────────────────


def _agg_col(df: pl.DataFrame, col: str, aggregation: str) -> Optional[float]:
    """Aggregate a column safely."""
    try:
        if col not in df.columns or df.height == 0:
            return None
        clean = df[col].drop_nulls()
        if len(clean) == 0:
            return None
        if aggregation == "sum":
            return float(clean.sum())
        elif aggregation == "mean":
            return float(clean.mean())
        elif aggregation == "median":
            return float(clean.median())
        elif aggregation == "max":
            return float(clean.max())
        elif aggregation == "min":
            return float(clean.min())
        else:
            return float(clean.sum())
    except Exception:
        return None


def _safe_title(name: str) -> str:
    """Convert column name to readable title."""
    return name.replace("_", " ").replace("-", " ").strip().title()


def _direction_clause(
    num_delta: float,
    num_name: str,
    den_delta: float,
    den_name: str,
) -> str:
    """Generate a clause explaining the ratio's components."""
    parts = []
    if abs(num_delta) > 3:
        parts.append(
            f"{num_name} {'grew' if num_delta > 0 else 'shrank'} {abs(num_delta):.0f}%"
        )
    if abs(den_delta) > 3:
        parts.append(
            f"{den_name} {'grew' if den_delta > 0 else 'shrank'} {abs(den_delta):.0f}%"
        )
    if parts:
        return "even though " + " and ".join(parts) + ". "
    return ""


# Singleton
surprising_patterns_engine = SurprisingPatternsEngine()
