"""
predictive_questions/templates.py — Question templates by analytical layer

Defines the question templates organized by analytical intent layer:
  - STRATEGIC: High-level overview questions (first 5 seconds)
  - DIAGNOSTIC: Operational health questions (this week/month)
  - ROOT_CAUSE: Investigative "why" questions
  - EXPLORATORY: Discovery questions for deeper analysis

Each template has slots for {metric}, {dimension}, {metric2} that get
filled by the generator from the dataset's actual columns.

Zero LLM calls — pure template filling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnalyticalLayer(str, Enum):
    """Layer of analytical intent for the predictive question."""

    STRATEGIC = "strategic"
    """High-level, what-do-I-need-to-know-in-5-seconds questions."""

    DIAGNOSTIC = "diagnostic"
    """How-is-this-period-going questions."""

    ROOT_CAUSE = "root_cause"
    """Why-did-this-happen investigative questions."""

    EXPLORATORY = "exploratory"
    """What-else-is-interesting discovery questions."""

    FORECAST = "forecast"
    """What-will-happen-next predictive questions."""


@dataclass
class QuestionTemplate:
    """A single question pattern with typed slots.

    The generator fills {metric}, {dimension}, {metric2} placeholders
    with actual column names from the dataset.
    """

    id: str
    """Unique template identifier (e.g. 'strat_total_by_dim')."""

    layer: AnalyticalLayer
    """Which analytical layer this template belongs to."""

    pattern: str
    """Template string with {metric}, {dimension}, {metric2} slots."""

    description: str
    """What kind of question this produces."""

    requires_metric: bool = True
    """Whether this template needs at least one measure column."""

    requires_dimension: bool = False
    """Whether this template needs at least one dimension column."""

    requires_time: bool = False
    """Whether this template needs a time column."""

    requires_two_metrics: bool = False
    """Whether this template needs two different measure columns."""

    complexity: str = "simple"
    """simple | moderate | complex — how hard is this to answer."""


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGIC LAYER — What do I need to know in 5 seconds?
# ═══════════════════════════════════════════════════════════════════════════════

STRATEGIC_TEMPLATES = [
    QuestionTemplate(
        id="strat_total",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="What is the total {metric}?",
        description="Overall value of a key metric",
        requires_metric=True,
        requires_dimension=False,
        complexity="simple",
    ),
    QuestionTemplate(
        id="strat_average",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="What is the average {metric}?",
        description="Average value of a key metric",
        requires_metric=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="strat_total_by_dim",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="What is the total {metric} by {dimension}?",
        description="Metric broken down by a category",
        requires_metric=True,
        requires_dimension=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="strat_highest_dim",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="Which {dimension} has the highest {metric}?",
        description="Top performer by metric",
        requires_metric=True,
        requires_dimension=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="strat_lowest_dim",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="Which {dimension} has the lowest {metric}?",
        description="Bottom performer by metric",
        requires_metric=True,
        requires_dimension=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="strat_count_records",
        layer=AnalyticalLayer.STRATEGIC,
        pattern="How many records are in the dataset?",
        description="Total record count",
        requires_metric=False,
        requires_dimension=False,
        complexity="simple",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC LAYER — How is this period going?
# ═══════════════════════════════════════════════════════════════════════════════

DIAGNOSTIC_TEMPLATES = [
    QuestionTemplate(
        id="diag_trend_over_time",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="How has {metric} changed over time?",
        description="Trend of a key metric over the time period",
        requires_metric=True,
        requires_time=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="diag_dim_trend",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="How does {metric} trend over time for each {dimension}?",
        description="Metric trend segmented by category",
        requires_metric=True,
        requires_dimension=True,
        requires_time=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="diag_distribution",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="What is the distribution of {metric} across {dimension}?",
        description="How metric values spread across categories",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="diag_top_n",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="What are the top 5 {dimension} by {metric}?",
        description="Ranked top categories by metric",
        requires_metric=True,
        requires_dimension=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="diag_bottom_n",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="What are the bottom 5 {dimension} by {metric}?",
        description="Ranked bottom categories by metric",
        requires_metric=True,
        requires_dimension=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="diag_metric_summary",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="What is the minimum, maximum, and average of {metric}?",
        description="Statistical summary of a metric",
        requires_metric=True,
        complexity="simple",
    ),
    QuestionTemplate(
        id="diag_period_comparison",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="How does {metric} compare across different periods?",
        description="Period-over-period metric comparison",
        requires_metric=True,
        requires_time=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="diag_share_by_dim",
        layer=AnalyticalLayer.DIAGNOSTIC,
        pattern="What percentage of total {metric} does each {dimension} represent?",
        description="Share/proportion breakdown by category",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ROOT CAUSE LAYER — Why did this happen?
# ═══════════════════════════════════════════════════════════════════════════════

ROOT_CAUSE_TEMPLATES = [
    QuestionTemplate(
        id="root_correlation",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="What is the relationship between {metric} and {metric2}?",
        description="Correlation between two metrics",
        requires_metric=True,
        requires_two_metrics=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="root_dim_driver",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="Which {dimension} drives the most change in {metric}?",
        description="Identify the key driver category for a metric",
        requires_metric=True,
        requires_dimension=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="root_outliers",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="Are there any outliers in {metric} by {dimension}?",
        description="Detect unusual values across categories",
        requires_metric=True,
        requires_dimension=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="root_anomaly_time",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="Were there any unusual spikes or drops in {metric} over time?",
        description="Anomaly detection in metric trends",
        requires_metric=True,
        requires_time=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="root_dim_interaction",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="How does the relationship between {metric} and {dimension} vary over time?",
        description="Metric-dimension relationship changing over time",
        requires_metric=True,
        requires_dimension=True,
        requires_time=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="root_metric_impact",
        layer=AnalyticalLayer.ROOT_CAUSE,
        pattern="When {metric} changes, which other metrics move with it?",
        description="Discover co-movements between metrics",
        requires_metric=True,
        requires_two_metrics=True,
        complexity="complex",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# EXPLORATORY LAYER — What else is interesting?
# ═══════════════════════════════════════════════════════════════════════════════

EXPLORATORY_TEMPLATES = [
    QuestionTemplate(
        id="explore_growth",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="Which {dimension} shows the highest growth in {metric}?",
        description="Fastest growing segments",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_decline",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="Which {dimension} shows the steepest decline in {metric}?",
        description="Declining segments needing attention",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_metric_heatmap",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="Show me a heatmap of {metric} across {dimension} over time",
        description="Multi-dimensional view of a metric",
        requires_metric=True,
        requires_dimension=True,
        requires_time=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="explore_dim_comparison",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="Compare {metric} performance across different {dimension} values",
        description="Side-by-side metric comparison",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_metric_ratio",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="What is the ratio of {metric} to {metric2}?",
        description="Efficiency ratio between two metrics",
        requires_metric=True,
        requires_two_metrics=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_rank",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="Rank all {dimension} by {metric} from highest to lowest",
        description="Full ranking of categories",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_cumulative",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="What is the cumulative {metric} over time?",
        description="Running total of a metric",
        requires_metric=True,
        requires_time=True,
        complexity="moderate",
    ),
    QuestionTemplate(
        id="explore_segments",
        layer=AnalyticalLayer.EXPLORATORY,
        pattern="How does {metric} differ between segments of {dimension}?",
        description="Segment-based metric comparison",
        requires_metric=True,
        requires_dimension=True,
        complexity="moderate",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# FORECAST LAYER — What will happen next?
# ═══════════════════════════════════════════════════════════════════════════════

FORECAST_TEMPLATES = [
    QuestionTemplate(
        id="forecast_metric",
        layer=AnalyticalLayer.FORECAST,
        pattern="What is the projected trend for {metric}?",
        description="Forecast future metric values",
        requires_metric=True,
        requires_time=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="forecast_dim",
        layer=AnalyticalLayer.FORECAST,
        pattern="Which {dimension} is expected to grow the most in {metric}?",
        description="Forecast growth by category",
        requires_metric=True,
        requires_dimension=True,
        complexity="complex",
    ),
    QuestionTemplate(
        id="forecast_seasonality",
        layer=AnalyticalLayer.FORECAST,
        pattern="Are there seasonal patterns in {metric} over time?",
        description="Detect recurring patterns",
        requires_metric=True,
        requires_time=True,
        complexity="complex",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ALL TEMPLATES — Combined list
# ═══════════════════════════════════════════════════════════════════════════════

ALL_TEMPLATES: list[QuestionTemplate] = (
    STRATEGIC_TEMPLATES
    + DIAGNOSTIC_TEMPLATES
    + ROOT_CAUSE_TEMPLATES
    + EXPLORATORY_TEMPLATES
    + FORECAST_TEMPLATES
)

TEMPLATES_BY_LAYER: dict[AnalyticalLayer, list[QuestionTemplate]] = {
    AnalyticalLayer.STRATEGIC: STRATEGIC_TEMPLATES,
    AnalyticalLayer.DIAGNOSTIC: DIAGNOSTIC_TEMPLATES,
    AnalyticalLayer.ROOT_CAUSE: ROOT_CAUSE_TEMPLATES,
    AnalyticalLayer.EXPLORATORY: EXPLORATORY_TEMPLATES,
    AnalyticalLayer.FORECAST: FORECAST_TEMPLATES,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Predictive Question Output Model
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PredictiveQuestion:
    """A single predictive question generated from the dataset."""

    id: str
    """Unique question identifier."""

    layer: AnalyticalLayer
    """Which analytical layer this question belongs to."""

    question: str
    """The natural language question text."""

    template_id: str
    """Which template generated this question."""

    metric: Optional[str] = None
    """The measure column used."""

    dimension: Optional[str] = None
    """The dimension column used (if any)."""

    metric2: Optional[str] = None
    """The second measure column used (if any)."""

    complexity: str = "simple"
    """simple | moderate | complex."""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "layer": self.layer.value,
            "question": self.question,
            "template_id": self.template_id,
            "metric": self.metric,
            "dimension": self.dimension,
            "metric2": self.metric2,
            "complexity": self.complexity,
        }
