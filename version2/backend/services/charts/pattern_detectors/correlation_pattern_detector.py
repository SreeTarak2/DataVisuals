from typing import List, Dict, Any, Optional
from itertools import combinations
import logging
import polars as pl

from .base_pattern_detector import BasePatternDetector

logger = logging.getLogger(__name__)


class CorrelationPatternDetector(BasePatternDetector):
    """
    Detects pairwise correlations between series and scale mismatches.

    For each pair of columns:
    - Computes Pearson correlation coefficient
    - Classifies: strong_positive, moderate_positive, strong_negative, moderate_negative
    - Detects scale ratio > 10x (signals dual-axis is needed)
    - Detects leading/lagging relationships (cross-correlation at lag 1)
    """

    STRONG_THRESHOLD = 0.75
    MODERATE_THRESHOLD = 0.4
    DUAL_AXIS_RATIO = 10.0  # If max(seriesA) / max(seriesB) > this → dual axis needed

    async def detect(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        patterns = []

        if len(columns) < 2:
            return patterns

        # Check scale ratios for all columns (dual axis detection)
        scale_pattern = self._detect_scale_mismatch(df, columns)
        if scale_pattern:
            patterns.append(scale_pattern)

        # Pairwise correlations
        for col_a, col_b in combinations(columns, 2):
            if col_a not in df.columns or col_b not in df.columns:
                continue

            vals_a = [self._safe_numeric(v) for v in df[col_a].to_list()]
            vals_b = [self._safe_numeric(v) for v in df[col_b].to_list()]

            if len(vals_a) < 4:
                continue

            corr = self._correlation_coefficient(vals_a, vals_b)

            if abs(corr) >= self.STRONG_THRESHOLD:
                strength = "strong"
                confidence = min(0.95, 0.75 + abs(corr) * 0.2)
            elif abs(corr) >= self.MODERATE_THRESHOLD:
                strength = "moderate"
                confidence = min(0.80, 0.5 + abs(corr) * 0.3)
            else:
                continue

            direction = "positive" if corr > 0 else "negative"
            lead_lag = self._detect_lead_lag(vals_a, vals_b, col_a, col_b)

            description = (
                f"{strength.title()} {direction} correlation between "
                f"{col_a} and {col_b} (r={corr:.2f})"
            )
            if lead_lag:
                description += f". {lead_lag}"

            pattern = self._build_pattern(
                pattern_type="correlation",
                series_involved=[col_a, col_b],
                description=description,
                confidence=confidence,
                metrics={
                    "pearson_r": round(corr, 3),
                    "strength": strength,
                    "direction": direction,
                    "lead_lag_note": lead_lag,
                }
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _detect_scale_mismatch(
        self,
        df: pl.DataFrame,
        columns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Detect if series have very different scales (dual-axis needed)."""
        ranges = {}
        for col in columns:
            if col not in df.columns:
                continue
            vals = [self._safe_numeric(v) for v in df[col].to_list() if v is not None]
            if not vals:
                continue
            col_range = max(vals) - min(vals)
            if col_range > 0:
                ranges[col] = col_range

        if len(ranges) < 2:
            return None

        max_range = max(ranges.values())
        min_range = min(ranges.values())

        if min_range == 0:
            return None

        ratio = max_range / min_range
        if ratio < self.DUAL_AXIS_RATIO:
            return None

        large_col = max(ranges, key=ranges.get)
        small_col = min(ranges, key=ranges.get)

        return self._build_pattern(
            pattern_type="scale_mismatch",
            series_involved=list(ranges.keys()),
            description=(
                f"Scale mismatch detected: {large_col} range is "
                f"{ratio:.0f}x larger than {small_col}. "
                f"Dual Y-axis recommended."
            ),
            confidence=0.95,
            metrics={
                "scale_ratio": round(ratio, 1),
                "large_scale_col": large_col,
                "small_scale_col": small_col,
                "suggests_dual_axis": True,
            }
        )

    def _detect_lead_lag(
        self,
        vals_a: List[float],
        vals_b: List[float],
        name_a: str,
        name_b: str,
        max_lag: int = 3
    ) -> Optional[str]:
        """Check if one series leads the other by 1-3 steps."""
        base_corr = abs(self._correlation_coefficient(vals_a, vals_b))
        best_lag = 0
        best_corr = base_corr

        n = len(vals_a)
        for lag in range(1, min(max_lag + 1, n // 4)):
            # A leads B
            corr_ab = abs(self._correlation_coefficient(vals_a[:-lag], vals_b[lag:]))
            # B leads A
            corr_ba = abs(self._correlation_coefficient(vals_b[:-lag], vals_a[lag:]))

            if corr_ab > best_corr + 0.05:
                best_corr = corr_ab
                best_lag = lag
            elif corr_ba > best_corr + 0.05:
                best_corr = corr_ba
                best_lag = -lag

        if best_lag > 0:
            return f"{name_a} leads {name_b} by {best_lag} periods"
        elif best_lag < 0:
            return f"{name_b} leads {name_a} by {abs(best_lag)} periods"

        return None
