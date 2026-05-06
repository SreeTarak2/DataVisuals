from typing import List, Dict, Any, Optional
import logging
import polars as pl

from .base_pattern_detector import BasePatternDetector

logger = logging.getLogger(__name__)


class AnomalyPatternDetector(BasePatternDetector):
    """
    Detects spikes, dips, and structural breaks in each series.

    Three detection methods:
    1. Z-score: Points > 2.5 std deviations from mean
    2. IQR fence: Points outside Q1 - 1.5*IQR or Q3 + 1.5*IQR
    3. Structural break: Mean of first half vs second half differs significantly
    """

    Z_THRESHOLD = 2.5
    BREAK_RATIO = 0.25  # 25% shift in mean signals a structural break

    async def detect(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        patterns = []

        x_labels = df[x_col].to_list() if x_col and x_col in df.columns else None

        for col in columns:
            if col not in df.columns:
                continue

            values = [self._safe_numeric(v) for v in df[col].to_list()]
            if len(values) < 6:
                continue

            spike_patterns = self._detect_spikes(values, col, x_labels)
            patterns.extend(spike_patterns)

            break_pattern = self._detect_structural_break(values, col, x_labels)
            if break_pattern:
                patterns.append(break_pattern)

        return patterns

    def _detect_spikes(
        self,
        values: List[float],
        col: str,
        x_labels: Optional[List]
    ) -> List[Dict[str, Any]]:
        """Detect individual spike/dip points using z-score."""
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
        std = variance ** 0.5

        if std == 0:
            return []

        spikes = []
        dips = []

        for i, v in enumerate(values):
            z = self._z_score(v, mean, std)
            if z >= self.Z_THRESHOLD:
                label = str(x_labels[i]) if x_labels else f"index {i}"
                if v > mean:
                    spikes.append({"index": i, "label": label, "value": v, "z": round(z, 2)})
                else:
                    dips.append({"index": i, "label": label, "value": v, "z": round(z, 2)})

        results = []

        if spikes:
            worst = max(spikes, key=lambda p: p["z"])
            pattern = self._build_pattern(
                pattern_type="spike",
                series_involved=[col],
                description=(
                    f"{col}: {len(spikes)} spike(s) detected. "
                    f"Largest at {worst['label']} "
                    f"(value={worst['value']:,.1f}, z={worst['z']}σ)"
                ),
                confidence=min(0.95, 0.65 + worst["z"] * 0.05),
                metrics={
                    "spike_count": len(spikes),
                    "largest_spike": worst,
                    "all_spikes": spikes[:5],
                    "series_mean": round(mean, 2),
                    "series_std": round(std, 2),
                }
            )
            if pattern:
                results.append(pattern)

        if dips:
            worst = max(dips, key=lambda p: p["z"])
            pattern = self._build_pattern(
                pattern_type="dip",
                series_involved=[col],
                description=(
                    f"{col}: {len(dips)} dip(s) detected. "
                    f"Largest at {worst['label']} "
                    f"(value={worst['value']:,.1f}, z={worst['z']}σ)"
                ),
                confidence=min(0.95, 0.65 + worst["z"] * 0.05),
                metrics={
                    "dip_count": len(dips),
                    "largest_dip": worst,
                    "all_dips": dips[:5],
                    "series_mean": round(mean, 2),
                    "series_std": round(std, 2),
                }
            )
            if pattern:
                results.append(pattern)

        return results

    def _detect_structural_break(
        self,
        values: List[float],
        col: str,
        x_labels: Optional[List]
    ) -> Optional[Dict[str, Any]]:
        """Detect a sustained level shift between first and second half."""
        mid = len(values) // 2
        if mid < 3:
            return None

        first_half = values[:mid]
        second_half = values[mid:]

        mean_first = sum(first_half) / len(first_half)
        mean_second = sum(second_half) / len(second_half)

        if mean_first == 0:
            return None

        shift_ratio = abs(mean_second - mean_first) / abs(mean_first)
        if shift_ratio < self.BREAK_RATIO:
            return None

        direction = "upward" if mean_second > mean_first else "downward"
        break_label = str(x_labels[mid]) if x_labels else f"index {mid}"

        return self._build_pattern(
            pattern_type="structural_break",
            series_involved=[col],
            description=(
                f"{col}: {direction} level shift detected around {break_label}. "
                f"Mean shifted {shift_ratio:.0%} "
                f"({mean_first:,.1f} → {mean_second:,.1f})"
            ),
            confidence=min(0.90, 0.55 + shift_ratio * 0.5),
            metrics={
                "direction": direction,
                "shift_ratio": round(shift_ratio, 3),
                "mean_before": round(mean_first, 2),
                "mean_after": round(mean_second, 2),
                "break_point_label": break_label,
                "break_point_index": mid,
            }
        )
