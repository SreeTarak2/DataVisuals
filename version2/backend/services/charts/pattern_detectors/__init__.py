"""
Pattern Detectors Package
=========================
Five specialized detectors for discovering patterns in multi-series data.

1. PanelPatternDetector — Faceting opportunities
2. TrendPatternDetector — Linear/exponential trends, reversals
3. SeasonalPatternDetector — Cycles, seasonality
4. AnomalyPatternDetector — Spikes, dips, structural breaks
5. CorrelationPatternDetector — Series comovement

All detectors inherit from BasePatternDetector abstract class.
"""

from .base_pattern_detector import BasePatternDetector
from .trend_pattern_detector import TrendPatternDetector
from .correlation_pattern_detector import CorrelationPatternDetector
from .anomaly_pattern_detector import AnomalyPatternDetector
from .seasonal_pattern_detector import SeasonalPatternDetector
from .panel_pattern_detector import PanelPatternDetector

__all__ = [
    "BasePatternDetector",
    "TrendPatternDetector",
    "CorrelationPatternDetector",
    "AnomalyPatternDetector",
    "SeasonalPatternDetector",
    "PanelPatternDetector",
]
