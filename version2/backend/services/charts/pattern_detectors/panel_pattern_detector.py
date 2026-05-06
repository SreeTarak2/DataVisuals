from typing import List, Dict, Any, Optional
import logging
import polars as pl

from .base_pattern_detector import BasePatternDetector

logger = logging.getLogger(__name__)


class PanelPatternDetector(BasePatternDetector):
    """
    Detects when faceting (small multiples) would be better than overlay.

    Triggers on:
    1. Too many series (>4) — overlay becomes unreadable
    2. High cardinality x-axis (>20 unique values) — single chart gets cluttered
    3. Series with very different variance — hard to read on shared axis without normalization
    4. Series that are truly independent (near-zero correlation with all others)
    """

    MAX_OVERLAY_SERIES = 4
    HIGH_CARDINALITY_THRESHOLD = 20
    INDEPENDENCE_THRESHOLD = 0.2  # |r| < 0.2 with all others = independent

    async def detect(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        patterns = []

        # 1. Too many series
        if len(columns) > self.MAX_OVERLAY_SERIES:
            pattern = self._build_pattern(
                pattern_type="panel_suggestion",
                series_involved=columns,
                description=(
                    f"{len(columns)} series detected. "
                    f"Overlay becomes unreadable above {self.MAX_OVERLAY_SERIES}. "
                    f"Small multiples (faceted) layout recommended."
                ),
                confidence=0.90,
                metrics={
                    "reason": "too_many_series",
                    "series_count": len(columns),
                    "max_overlay": self.MAX_OVERLAY_SERIES,
                    "suggests_facet": True,
                }
            )
            if pattern:
                patterns.append(pattern)

        # 2. High cardinality x-axis
        if x_col and x_col in df.columns:
            n_unique = df[x_col].n_unique()
            if n_unique > self.HIGH_CARDINALITY_THRESHOLD:
                pattern = self._build_pattern(
                    pattern_type="panel_suggestion",
                    series_involved=columns,
                    description=(
                        f"X-axis '{x_col}' has {n_unique} unique values. "
                        f"Chart will be cluttered. "
                        f"Consider faceting by a categorical dimension or aggregating."
                    ),
                    confidence=0.80,
                    metrics={
                        "reason": "high_cardinality_x",
                        "x_col": x_col,
                        "unique_values": n_unique,
                        "threshold": self.HIGH_CARDINALITY_THRESHOLD,
                        "suggests_facet": True,
                    }
                )
                if pattern:
                    patterns.append(pattern)

        # 3. Variance spread — if one series has 10x the variance, it dominates visually
        variance_pattern = self._detect_variance_dominance(df, columns)
        if variance_pattern:
            patterns.append(variance_pattern)

        # 4. Independent series — if no series correlate, faceting tells cleaner stories
        if len(columns) >= 3:
            independence_pattern = self._detect_independent_series(df, columns)
            if independence_pattern:
                patterns.append(independence_pattern)

        return patterns

    def _detect_variance_dominance(
        self,
        df: pl.DataFrame,
        columns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Detect if one series visually dominates due to variance scale."""
        variances = {}
        for col in columns:
            if col not in df.columns:
                continue
            vals = [self._safe_numeric(v) for v in df[col].to_list()]
            if len(vals) < 2:
                continue
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)
            if var > 0:
                variances[col] = var

        if len(variances) < 2:
            return None

        max_var = max(variances.values())
        min_var = min(variances.values())
        ratio = max_var / min_var

        if ratio < 100:  # 10x std deviation difference
            return None

        dominant = max(variances, key=variances.get)
        return self._build_pattern(
            pattern_type="panel_suggestion",
            series_involved=list(variances.keys()),
            description=(
                f"'{dominant}' has {ratio:.0f}x more variance than other series. "
                f"It will dominate the chart visually. "
                f"Faceting or normalization recommended."
            ),
            confidence=0.75,
            metrics={
                "reason": "variance_dominance",
                "dominant_series": dominant,
                "variance_ratio": round(ratio, 1),
                "suggests_facet": True,
            }
        )

    def _detect_independent_series(
        self,
        df: pl.DataFrame,
        columns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Detect if series are all independent (no correlation) — separate panels tell cleaner stories."""
        independent_cols = []

        for col in columns:
            if col not in df.columns:
                continue

            vals = [self._safe_numeric(v) for v in df[col].to_list()]
            others = [
                c for c in columns
                if c != col and c in df.columns
            ]

            max_corr = 0.0
            for other in others:
                other_vals = [self._safe_numeric(v) for v in df[other].to_list()]
                r = abs(self._correlation_coefficient(vals, other_vals))
                max_corr = max(max_corr, r)

            if max_corr < self.INDEPENDENCE_THRESHOLD:
                independent_cols.append(col)

        if len(independent_cols) < 2:
            return None

        return self._build_pattern(
            pattern_type="panel_suggestion",
            series_involved=independent_cols,
            description=(
                f"{len(independent_cols)} series are statistically independent "
                f"(|r| < {self.INDEPENDENCE_THRESHOLD} with all others). "
                f"Separate panels will tell cleaner individual stories."
            ),
            confidence=0.70,
            metrics={
                "reason": "independent_series",
                "independent_cols": independent_cols,
                "independence_threshold": self.INDEPENDENCE_THRESHOLD,
                "suggests_facet": True,
            }
        )
