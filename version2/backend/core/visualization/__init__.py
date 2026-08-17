"""
DataSage Visualization Intent Schema (VIS)
============================================
Renderer-agnostic visualization contract.

The backend produces VIS objects. Frontend adapters translate VIS into
Plotly, ECharts, or any other visualization library.
"""

from .visualization_schema import (
    VIS,
    VISDataSeries,
    VISDataSeriesType,
    VISAxis,
    VISAxisType,
    VISInteraction,
    VISAnalytics,
    VISNarrative,
    SeriesStrategyType,
    AnalysisIntentType,
    VISSeriesCollection,
    VIFacetConfig,
    VISPointIntelligence,
    VISPointIntelligenceStats,
    VISPointIntelligencePoint,
    VISNode,
    VISLink,
    VISVariantConfig,
    __all__ as _schema_all,
)

from .visualization_validator import (
    VISValidator,
    ValidationResult,
)

from .visualization_schema import (
    ValidationSeverity,
)

from .visualization_factory import (
    VISFactory,
)

from .compat_shim import (
    VISCompatibilityShim,
    PlotlyConverter,
)

__all__ = [
    # Core models
    "VIS",
    "VISDataSeries",
    "VISDataSeriesType",
    "VISAxis",
    "VISAxisType",
    "VISInteraction",
    "VISAnalytics",
    "VISNarrative",
    "SeriesStrategyType",
    "AnalysisIntentType",
    "VISSeriesCollection",
    "VIFacetConfig",
    "VISPointIntelligence",
    "VISPointIntelligenceStats",
    "VISPointIntelligencePoint",
    # ECharts-native models
    "VISNode",
    "VISLink",
    "VISVariantConfig",
    # Validation
    "VISValidator",
    "ValidationResult",
    "ValidationSeverity",
    # Factory
    "VISFactory",
    # Compatibility
    "VISCompatibilityShim",
    "PlotlyConverter",
]
