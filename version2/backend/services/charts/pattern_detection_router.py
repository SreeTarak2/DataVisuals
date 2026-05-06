"""
Pattern Detection Router
========================
Orchestrates multi-detector pattern discovery from time series data.

Pipeline:
    DataFrame → Panel Pattern Detector
             → Trend Pattern Detector
             → Seasonal Pattern Detector
             → Anomaly Pattern Detector
             → Correlation Pattern Detector
             → Aggregated Results

Each detector runs independently and returns CrossSeriesPattern objects.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import polars as pl
from dataclasses import asdict

logger = logging.getLogger(__name__)


class PatternDetectionRouter:
    """
    Runs all 5 pattern detectors, aggregates results.

    Detectors:
    1. PanelPatternDetector — Identify faceting suggestions
    2. TrendPatternDetector — Linear/exponential trends, reversals
    3. SeasonalPatternDetector — Repeating patterns, cycles
    4. AnomalyPatternDetector — Spikes, dips, breaks
    5. CorrelationPatternDetector — Series moving together
    """

    def __init__(self):
        """Initialize detector instances."""
        self._detectors = {}

    async def run_detection(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str,
        time_indexed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: Run all detectors and aggregate.

        Args:
            df: Polars DataFrame with data
            columns: List of metric columns to analyze
            x_col: X-axis (time/category) column name
            time_indexed: If True, treat x_col as time series

        Returns:
            List of pattern dicts ready for MultiSeriesViewSpec:
            [
                {
                    "pattern_type": "trend",
                    "series_involved": ["Revenue", "Cost"],
                    "description": "Linear growth detected",
                    "confidence": 0.95,
                    "metrics": {"r_squared": 0.92, "slope": 1500}
                },
                ...
            ]

        Raises:
            ValueError: If columns not in df or x_col invalid
        """
        logger.info(f"Pattern detection: {len(columns)} series, time_indexed={time_indexed}")

        # Validate input
        self._validate_input(df, columns, x_col)

        patterns = []

        try:
            # Run all detectors independently
            panel_patterns = await self._detect_paneling(df, columns, x_col)
            patterns.extend(panel_patterns)

            if time_indexed:
                trend_patterns = await self._detect_trends(df, columns, x_col)
                patterns.extend(trend_patterns)

                seasonal_patterns = await self._detect_seasonality(df, columns, x_col)
                patterns.extend(seasonal_patterns)

                anomaly_patterns = await self._detect_anomalies(df, columns, x_col)
                patterns.extend(anomaly_patterns)

            # Correlations work on any data
            correlation_patterns = await self._detect_correlations(df, columns)
            patterns.extend(correlation_patterns)

            logger.info(f"Detected {len(patterns)} patterns")
            return patterns

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}", exc_info=True)
            raise

    def _validate_input(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str
    ) -> None:
        """Validate DataFrame and column names."""
        if df.is_empty():
            raise ValueError("DataFrame is empty")

        if not all(col in df.columns for col in columns):
            missing = [c for c in columns if c not in df.columns]
            raise ValueError(f"Columns not found: {missing}")

        if x_col not in df.columns:
            raise ValueError(f"X column not found: {x_col}")

    async def _detect_paneling(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str
    ) -> List[Dict[str, Any]]:
        """
        Detect paneling (faceting) opportunities.

        Heuristic: If many unique values in category, suggest faceting.
        """
        from .pattern_detectors.panel_pattern_detector import PanelPatternDetector

        detector = PanelPatternDetector()
        return await detector.detect(df, columns, x_col)

    async def _detect_trends(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str
    ) -> List[Dict[str, Any]]:
        """
        Detect trend patterns (linear, exponential, reversal).
        """
        from .pattern_detectors.trend_pattern_detector import TrendPatternDetector

        detector = TrendPatternDetector()
        return await detector.detect(df, columns, x_col)

    async def _detect_seasonality(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str
    ) -> List[Dict[str, Any]]:
        """
        Detect seasonal/cyclical patterns.
        """
        from .pattern_detectors.seasonal_pattern_detector import SeasonalPatternDetector

        detector = SeasonalPatternDetector()
        return await detector.detect(df, columns, x_col)

    async def _detect_anomalies(
        self,
        df: pl.DataFrame,
        columns: List[str],
        x_col: str
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies (spikes, dips, structural breaks).
        """
        from .pattern_detectors.anomaly_pattern_detector import AnomalyPatternDetector

        detector = AnomalyPatternDetector()
        return await detector.detect(df, columns, x_col)

    async def _detect_correlations(
        self,
        df: pl.DataFrame,
        columns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Detect correlation patterns (series moving together).
        """
        from .pattern_detectors.correlation_pattern_detector import CorrelationPatternDetector

        detector = CorrelationPatternDetector()
        return await detector.detect(df, columns)


# Singleton instance
pattern_detection_router = PatternDetectionRouter()
