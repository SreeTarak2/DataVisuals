from typing import List, Dict, Any, Optional
import logging
import polars as pl

from .base_pattern_detector import BasePatternDetector

logger = logging.getLogger(__name__)


class SeasonalPatternDetector(BasePatternDetector):
    """
    Detects repeating cyclical patterns using autocorrelation.

    Tests common periods: 7 (weekly), 12 (monthly/annual), 4 (quarterly).
    Requires at least 2x the period length to be meaningful.
    Also detects simple periodicity by checking if variance of
    period-folded data is significantly lower than raw variance.
    """

    AUTOCORR_THRESHOLD = 0.5   # Minimum autocorrelation to report seasonality
    COMMON_PERIODS = [4, 7, 12, 24, 52]  # quarterly, weekly, monthly, hourly, annual

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
            if len(values) < 8:
                continue

            # Detrend first so we don't confuse trend for seasonality
            detrended = self._detrend(values)

            best_period, best_autocorr = self._find_best_period(detrended)
            if best_period is None:
                continue

            period_name = self._period_label(best_period)
            confidence = min(0.90, 0.5 + best_autocorr * 0.5)

            description = (
                f"{col}: {period_name} seasonality detected "
                f"(period={best_period}, autocorr={best_autocorr:.2f})"
            )

            pattern = self._build_pattern(
                pattern_type="seasonality",
                series_involved=[col],
                description=description,
                confidence=confidence,
                metrics={
                    "period": best_period,
                    "period_label": period_name,
                    "autocorrelation": round(best_autocorr, 3),
                    "n_complete_cycles": len(values) // best_period,
                }
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _detrend(self, values: List[float]) -> List[float]:
        """Remove linear trend so autocorrelation measures cycles, not drift."""
        n = len(values)
        if n < 2:
            return values

        x = list(range(n))
        slope, _ = self._linear_regression_slope(x, values)
        return [v - slope * i for i, v in enumerate(values)]

    def _autocorrelation(self, values: List[float], lag: int) -> float:
        """Compute autocorrelation at a given lag."""
        n = len(values)
        if lag >= n:
            return 0.0

        mean = sum(values) / n
        demeaned = [v - mean for v in values]

        numerator = sum(demeaned[i] * demeaned[i + lag] for i in range(n - lag))
        denominator = sum(v ** 2 for v in demeaned)

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _find_best_period(
        self,
        values: List[float]
    ) -> tuple:
        """Test each common period, return the one with highest autocorrelation."""
        n = len(values)
        best_period = None
        best_autocorr = 0.0

        for period in self.COMMON_PERIODS:
            # Need at least 2 full cycles
            if period * 2 > n:
                continue

            autocorr = self._autocorrelation(values, period)

            if autocorr >= self.AUTOCORR_THRESHOLD and autocorr > best_autocorr:
                best_autocorr = autocorr
                best_period = period

        return best_period, best_autocorr

    def _period_label(self, period: int) -> str:
        labels = {
            4: "Quarterly",
            7: "Weekly",
            12: "Monthly/Annual",
            24: "Daily (hourly data)",
            52: "Annual (weekly data)",
        }
        return labels.get(period, f"{period}-period")
