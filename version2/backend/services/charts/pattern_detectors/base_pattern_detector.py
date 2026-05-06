"""
Base Pattern Detector
=====================
Abstract base class for all pattern detection algorithms.

Interface:
    async def detect(df, columns, [x_col]) -> List[Dict]

Each detector:
1. Validates input
2. Processes data (rolling windows, diffs, correlations, etc.)
3. Returns structured CrossSeriesPattern objects
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BasePatternDetector(ABC):
    """
    Abstract base for pattern detectors.

    All detectors must implement detect() to return list of pattern dicts.
    """

    def __init__(self, confidence_threshold: float = 0.5):
        """
        Initialize detector.

        Args:
            confidence_threshold: Minimum confidence (0-1) to report pattern
        """
        self.confidence_threshold = confidence_threshold

    @abstractmethod
    async def detect(
        self,
        df,
        columns: List[str],
        x_col: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns in data.

        Args:
            df: Polars DataFrame
            columns: List of metric columns to analyze
            x_col: Optional x-axis column (name, date, etc.)

        Returns:
            List of pattern dicts:
            [
                {
                    "pattern_type": "trend",
                    "series_involved": ["Revenue", "Cost"],
                    "description": "Linear growth detected",
                    "confidence": 0.92,
                    "metrics": {
                        "slope": 1500,
                        "r_squared": 0.91,
                        "p_value": 0.001
                    }
                },
                ...
            ]
        """
        pass

    def _build_pattern(
        self,
        pattern_type: str,
        series_involved: List[str],
        description: str,
        confidence: float,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build standardized pattern object.

        Args:
            pattern_type: Pattern category (trend, seasonal, anomaly, etc.)
            series_involved: Which series show this pattern
            description: Human-readable description
            confidence: 0-1 confidence score
            metrics: Dict of statistical metrics

        Returns:
            Structured pattern dict ready for MultiSeriesViewSpec
        """
        if confidence < self.confidence_threshold:
            return None

        pattern = {
            "pattern_type": pattern_type,
            "series_involved": series_involved,
            "description": description,
            "confidence": min(confidence, 1.0),
            "metrics": metrics or {}
        }

        logger.debug(f"Built pattern: {pattern_type} ({confidence:.2f})")
        return pattern

    def _safe_numeric(self, value: Any, default: float = 0.0) -> float:
        """
        Safely convert value to float.

        Args:
            value: Value to convert
            default: Default if conversion fails

        Returns:
            Float value or default
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _percentile_change(
        self,
        series: List[float],
        window_size: int = 4
    ) -> float:
        """
        Calculate percentage change from first to last.

        Args:
            series: List of numeric values
            window_size: Ignored in base, used by subclasses

        Returns:
            Percentage change (0.0 to 1.0)
        """
        if len(series) < 2:
            return 0.0

        first = self._safe_numeric(series[0])
        last = self._safe_numeric(series[-1])

        if first == 0:
            return 0.0

        return (last - first) / first

    def _moving_average(
        self,
        series: List[float],
        window: int
    ) -> List[float]:
        """
        Calculate moving average.

        Args:
            series: Input values
            window: Window size

        Returns:
            Moving average values
        """
        if len(series) < window:
            return series

        ma = []
        for i in range(len(series) - window + 1):
            window_values = series[i : i + window]
            avg = sum(window_values) / len(window_values)
            ma.append(avg)

        return ma

    def _linear_regression_slope(
        self,
        x: List[float],
        y: List[float]
    ) -> Tuple[float, float]:
        """
        Calculate linear regression slope and r-squared.

        Args:
            x: X values (indices or time)
            y: Y values (metric)

        Returns:
            (slope, r_squared)
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0, 0.0

        try:
            import numpy as np

            x_arr = np.array([self._safe_numeric(v) for v in x])
            y_arr = np.array([self._safe_numeric(v) for v in y])

            # Linear regression
            coeffs = np.polyfit(x_arr, y_arr, 1)
            slope = coeffs[0]

            # R-squared
            y_pred = np.polyval(coeffs, x_arr)
            ss_res = np.sum((y_arr - y_pred) ** 2)
            ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            return slope, r_squared

        except ImportError:
            logger.warning("NumPy not available, using fallback regression")
            return 0.0, 0.0
        except Exception as e:
            logger.warning(f"Regression calculation failed: {e}")
            return 0.0, 0.0

    def _correlation_coefficient(
        self,
        series1: List[float],
        series2: List[float]
    ) -> float:
        """
        Calculate Pearson correlation coefficient.

        Args:
            series1: First series
            series2: Second series

        Returns:
            Correlation (-1 to 1)
        """
        if len(series1) != len(series2) or len(series1) < 2:
            return 0.0

        try:
            import numpy as np

            s1 = np.array([self._safe_numeric(v) for v in series1])
            s2 = np.array([self._safe_numeric(v) for v in series2])

            return float(np.corrcoef(s1, s2)[0, 1])

        except (ImportError, ValueError):
            logger.warning("NumPy correlation calculation failed")
            return 0.0

    def _z_score(self, value: float, mean: float, std: float) -> float:
        """
        Calculate z-score (standard deviations from mean).

        Args:
            value: Data point
            mean: Series mean
            std: Series standard deviation

        Returns:
            Z-score (higher = more anomalous)
        """
        if std == 0:
            return 0.0

        return abs((value - mean) / std)


# Type hint for return type
from typing import Tuple
