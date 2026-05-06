from typing import List, Dict, Any, Optional
import logging
import polars as pl

from .base_pattern_detector import BasePatternDetector

logger = logging.getLogger(__name__)


class TrendPatternDetector(BasePatternDetector):
    """
    Detects linear trends, exponential growth, and trend reversals.

    For each series:
    - Fits a linear regression, reports slope + R²
    - Checks for trend reversal (direction change in second half)
    - Classifies: strong_up, moderate_up, flat, moderate_down, strong_down
    """

    SLOPE_STRONG = 0.05    # >5% of mean per step = strong
    SLOPE_MODERATE = 0.01  # >1% of mean per step = moderate
    R2_THRESHOLD = 0.5     # Minimum R² to call it a real trend

    async def detect(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        patterns = []

        for col in columns:
            if col not in df.columns:
                continue

            values = [self._safe_numeric(v) for v in df[col].to_list()]
            if len(values) < 4:
                continue

            x = list(range(len(values)))
            slope, r_squared = self._linear_regression_slope(x, values)

            if r_squared < self.R2_THRESHOLD:
                continue

            mean_val = sum(values) / len(values) if values else 1.0
            if mean_val == 0:
                continue

            # Normalize slope relative to series magnitude
            relative_slope = abs(slope) / abs(mean_val)

            if relative_slope >= self.SLOPE_STRONG:
                strength = "strong"
                confidence = min(0.95, 0.7 + r_squared * 0.25)
            elif relative_slope >= self.SLOPE_MODERATE:
                strength = "moderate"
                confidence = min(0.85, 0.55 + r_squared * 0.3)
            else:
                continue  # Not worth reporting

            direction = "upward" if slope > 0 else "downward"
            total_change = self._percentile_change(values)
            reversal = self._detect_reversal(values)

            description = (
                f"{col}: {strength} {direction} trend "
                f"({total_change:+.1%} total change, R²={r_squared:.2f})"
            )
            if reversal:
                description += " with reversal in second half"

            pattern = self._build_pattern(
                pattern_type="trend",
                series_involved=[col],
                description=description,
                confidence=confidence,
                metrics={
                    "slope": round(slope, 4),
                    "r_squared": round(r_squared, 3),
                    "direction": direction,
                    "strength": strength,
                    "total_change_pct": round(total_change * 100, 1),
                    "has_reversal": reversal,
                    "mean_value": round(mean_val, 2),
                }
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _detect_reversal(self, values: List[float]) -> bool:
        """Returns True if the trend direction flips between first and second half."""
        mid = len(values) // 2
        if mid < 2:
            return False

        first_half = values[:mid]
        second_half = values[mid:]

        x_first = list(range(len(first_half)))
        x_second = list(range(len(second_half)))

        slope_first, r2_first = self._linear_regression_slope(x_first, first_half)
        slope_second, r2_second = self._linear_regression_slope(x_second, second_half)

        # Only flag reversal if both halves have meaningful trends
        if r2_first < 0.3 or r2_second < 0.3:
            return False

        return (slope_first > 0) != (slope_second > 0)
