"""
KPI & Financial Metrics Schemas
-------------------------------
Schemas for:
- KPI definitions and calculations
- Financial metric templates (SaaS, E-commerce, etc.)
- Pre-built dashboard templates for financial services
- Metric suggestions based on column detection

Target Market: Financial Services (Fintechs, Accounting Firms, etc.)
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum


# ---------------------------------------------------
# Base Config
# ---------------------------------------------------
class KPIBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


# ---------------------------------------------------
# Enums for KPI Types
# ---------------------------------------------------
class KPICategory(str, Enum):
    """Categories of financial KPIs."""

    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    FINANCE = "finance"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    HR = "hr"
    EDUCATION = "education"
    MANUFACTURING = "manufacturing"
    LOGISTICS = "logistics"
    AUTOMOTIVE = "automotive"
    CUSTOM = "custom"


class AggregationType(str, Enum):
    """How to aggregate values for KPI calculation."""

    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    LAST = "last"
    FIRST = "first"
    NUNIQUE = "nunique"
    CUSTOM = "custom"


class TrendDirection(str, Enum):
    """Expected trend direction for KPI health."""

    UP_IS_GOOD = "up_is_good"  # e.g., Revenue, MRR
    DOWN_IS_GOOD = "down_is_good"  # e.g., Churn, CAC
    STABLE_IS_GOOD = "stable_is_good"  # e.g., Retention Rate


class ComparisonPeriod(str, Enum):
    """Period for comparison calculations."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


# ---------------------------------------------------
# KPI Definition Models
# ---------------------------------------------------
class KPIFormula(KPIBaseModel):
    """
    Formula definition for calculated KPIs.
    Supports simple aggregations and complex formulas.
    """

    formula_type: Literal["simple", "ratio", "growth", "custom"] = "simple"

    # For simple aggregations (SUM, MEAN, etc.)
    column: Optional[str] = None
    aggregation: Optional[AggregationType] = None

    # For ratios (e.g., LTV/CAC)
    numerator_column: Optional[str] = None
    numerator_aggregation: Optional[AggregationType] = None
    denominator_column: Optional[str] = None
    denominator_aggregation: Optional[AggregationType] = None

    # For growth calculations (e.g., MoM growth)
    comparison_period: Optional[ComparisonPeriod] = None

    # For custom formulas (Python expression)
    custom_expression: Optional[str] = None


class KPIThreshold(BaseModel):
    """Threshold for KPI health/alerting."""

    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None


class KPIDefinition(BaseModel):
    """
    Complete definition of a KPI metric.
    Can be user-defined or from a template.
    """

    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    category: KPICategory = KPICategory.CUSTOM
    formula: KPIFormula

    # Display
    format: str = "number"  # number, currency, percentage, duration
    currency: Optional[str] = "USD"
    decimals: int = 2
    prefix: Optional[str] = None  # e.g., "$"
    suffix: Optional[str] = None  # e.g., "%"

    # Health tracking
    trend_direction: TrendDirection = TrendDirection.UP_IS_GOOD
    thresholds: Optional[KPIThreshold] = None

    # Metadata
    icon: Optional[str] = None  # Lucide icon name
    color: Optional[str] = None  # Tailwind color class


# ---------------------------------------------------
# Pre-Built KPI Templates
# ---------------------------------------------------
class SaaSMetrics(BaseModel):
    """SaaS-specific KPI definitions."""

    mrr: KPIDefinition = KPIDefinition(
        name="Monthly Recurring Revenue (MRR)",
        description="Total predictable revenue per month",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    )

    arr: KPIDefinition = KPIDefinition(
        name="Annual Recurring Revenue (ARR)",
        description="MRR × 12 - annualized revenue",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="custom", custom_expression="mrr * 12"),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    )

    churn_rate: KPIDefinition = KPIDefinition(
        name="Churn Rate",
        description="Percentage of customers lost per period",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=5.0, critical_max=10.0),
        icon="user-minus",
        color="red",
    )

    ltv: KPIDefinition = KPIDefinition(
        name="Customer Lifetime Value (LTV)",
        description="Average revenue per customer over lifetime",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="custom", custom_expression="arpu / churn_rate"
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="users",
        color="blue",
    )

    cac: KPIDefinition = KPIDefinition(
        name="Customer Acquisition Cost (CAC)",
        description="Cost to acquire one customer",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="target",
        color="orange",
    )

    ltv_cac_ratio: KPIDefinition = KPIDefinition(
        name="LTV/CAC Ratio",
        description="Return on customer acquisition (target: 3:1)",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="custom", custom_expression="ltv / cac"),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=2.0, critical_min=1.0),
        icon="scale",
        color="purple",
    )

    net_revenue_retention: KPIDefinition = KPIDefinition(
        name="Net Revenue Retention (NRR)",
        description="Revenue from existing customers (expansion - churn)",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="growth", comparison_period=ComparisonPeriod.MONTH
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=100.0, critical_min=90.0),
        icon="refresh-cw",
        color="teal",
    )

    burn_rate: KPIDefinition = KPIDefinition(
        name="Burn Rate",
        description="Monthly cash consumption",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="flame",
        color="red",
    )

    runway: KPIDefinition = KPIDefinition(
        name="Runway",
        description="Months until cash runs out",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="custom", custom_expression="cash_balance / burn_rate"
        ),
        format="number",
        suffix=" months",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=12.0, critical_min=6.0),
        icon="clock",
        color="amber",
    )


class EcommerceMetrics(BaseModel):
    """E-commerce-specific KPI definitions."""

    revenue: KPIDefinition = KPIDefinition(
        name="Total Revenue",
        description="Total sales revenue",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="shopping-cart",
        color="green",
    )

    aov: KPIDefinition = KPIDefinition(
        name="Average Order Value (AOV)",
        description="Average revenue per order",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="receipt",
        color="blue",
    )

    conversion_rate: KPIDefinition = KPIDefinition(
        name="Conversion Rate",
        description="Visitors who completed purchase",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="percent",
        color="purple",
    )

    cart_abandonment: KPIDefinition = KPIDefinition(
        name="Cart Abandonment Rate",
        description="Percentage of carts not converted",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(formula_type="ratio"),
        format="percentage",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="shopping-bag",
        color="orange",
    )

    customer_retention: KPIDefinition = KPIDefinition(
        name="Customer Retention Rate",
        description="Returning customers percentage",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(formula_type="ratio"),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="user-check",
        color="teal",
    )

    gross_margin: KPIDefinition = KPIDefinition(
        name="Gross Margin",
        description="(Revenue - COGS) / Revenue",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(
            formula_type="custom", custom_expression="(revenue - cogs) / revenue * 100"
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    )


class FinanceMetrics(BaseModel):
    """General finance KPI definitions."""

    gross_profit: KPIDefinition = KPIDefinition(
        name="Gross Profit",
        description="Revenue minus cost of goods sold",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="custom", custom_expression="revenue - cogs"),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    )

    net_profit: KPIDefinition = KPIDefinition(
        name="Net Profit",
        description="Total profit after all expenses",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    )

    operating_expenses: KPIDefinition = KPIDefinition(
        name="Operating Expenses (OPEX)",
        description="Total operational costs",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="credit-card",
        color="red",
    )

    ebitda: KPIDefinition = KPIDefinition(
        name="EBITDA",
        description="Earnings before interest, taxes, depreciation & amortization",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="custom"),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="bar-chart-2",
        color="blue",
    )

    cash_flow: KPIDefinition = KPIDefinition(
        name="Net Cash Flow",
        description="Cash inflows minus outflows",
        category=KPICategory.FINANCE,
        formula=KPIFormula(
            formula_type="custom", custom_expression="cash_inflows - cash_outflows"
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="activity",
        color="teal",
    )

    accounts_receivable_aging: KPIDefinition = KPIDefinition(
        name="AR Aging (Days)",
        description="Average days to collect receivables",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" days",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=45.0, critical_max=90.0),
        icon="calendar",
        color="orange",
    )


# ---------------------------------------------------
# KPI Template (Pre-built Dashboard)
# ---------------------------------------------------
class KPITemplateComponent(BaseModel):
    """Single component in a KPI template."""

    kpi_id: str  # References KPIDefinition.id or built-in name
    position: int  # Order in dashboard
    span: int = 1  # Grid columns to span (1-4)
    show_trend: bool = True
    show_sparkline: bool = False
    comparison_period: ComparisonPeriod = ComparisonPeriod.MONTH


class KPITemplate(BaseModel):
    """
    Pre-built KPI dashboard template.
    Users can apply these to their datasets.
    """

    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category: KPICategory

    # Template components
    kpis: List[KPITemplateComponent] = []

    # Column mapping hints (for auto-detection)
    required_columns: List[str] = []  # Must have these column types
    optional_columns: List[str] = []  # Nice to have

    # Sample data hints
    example_columns: Dict[str, str] = {}  # column_type -> example column name

    # Metadata
    icon: Optional[str] = None
    preview_image: Optional[str] = None
    popularity: int = 0  # Usage count

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------
# KPI Calculation Request/Response
# ---------------------------------------------------
class KPIColumnMapping(BaseModel):
    """Maps KPI formula columns to actual dataset columns."""

    kpi_id: str
    column_mappings: Dict[str, str]  # formula_column -> dataset_column
    date_column: Optional[str] = None  # For time-based calculations


class KPICalculateRequest(BaseModel):
    """Request to calculate KPIs for a dataset."""

    dataset_id: str
    kpi_ids: List[str]  # Which KPIs to calculate
    column_mappings: List[KPIColumnMapping]

    # Time range
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    group_by_period: Optional[ComparisonPeriod] = None


class KPICalculationResult(BaseModel):
    """Result of a single KPI calculation."""

    kpi_id: str
    kpi_name: str
    value: float
    formatted_value: str  # e.g., "$1,234.56" or "12.5%"

    # Trend comparison
    previous_value: Optional[float] = None
    change_value: Optional[float] = None
    change_percentage: Optional[float] = None
    trend: Optional[Literal["up", "down", "stable"]] = None

    # Health status
    status: Literal["healthy", "warning", "critical"] = "healthy"

    # Time series (if grouped)
    time_series: Optional[List[Dict[str, Any]]] = None


class KPICalculateResponse(BaseModel):
    """Response with all calculated KPIs."""

    dataset_id: str
    calculated_at: datetime
    period: Optional[str] = None  # e.g., "2024-01" for monthly

    results: List[KPICalculationResult]

    # Summary
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0


# ---------------------------------------------------
# Auto-Detection & Suggestions
# ---------------------------------------------------
class ColumnTypeDetection(BaseModel):
    """Detected column type for KPI mapping."""

    column_name: str
    detected_type: str  # revenue, cost, date, customer_id, etc.
    confidence: float  # 0.0 - 1.0
    sample_values: List[Any] = []


class KPISuggestion(BaseModel):
    """Suggested KPI based on detected columns."""

    kpi: KPIDefinition
    suggested_mappings: Dict[str, str]  # formula_column -> dataset_column
    confidence: float  # 0.0 - 1.0
    reason: str  # Why this KPI is suggested


class KPISuggestResponse(BaseModel):
    """Response with suggested KPIs for a dataset."""

    dataset_id: str
    detected_columns: List[ColumnTypeDetection]
    suggested_kpis: List[KPISuggestion]
    suggested_template: Optional[KPITemplate] = None


# ---------------------------------------------------
# Saved KPI Configurations
# ---------------------------------------------------
class SavedKPIConfig(BaseModel):
    """User's saved KPI configuration for a dataset."""

    id: Optional[str] = None
    user_id: str
    dataset_id: str

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

    # KPI definitions and mappings
    kpis: List[KPIDefinition] = []
    column_mappings: List[KPIColumnMapping] = []

    # From template?
    template_id: Optional[str] = None

    # Auto-refresh settings
    auto_refresh: bool = False
    refresh_interval: Optional[ComparisonPeriod] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------
# Export
# ---------------------------------------------------
__all__ = [
    # Enums
    "KPICategory",
    "AggregationType",
    "TrendDirection",
    "ComparisonPeriod",
    # Core models
    "KPIFormula",
    "KPIThreshold",
    "KPIDefinition",
    # Pre-built metrics
    "SaaSMetrics",
    "EcommerceMetrics",
    "FinanceMetrics",
    # Templates
    "KPITemplateComponent",
    "KPITemplate",
    # Calculation
    "KPIColumnMapping",
    "KPICalculateRequest",
    "KPICalculationResult",
    "KPICalculateResponse",
    # Auto-detection
    "ColumnTypeDetection",
    "KPISuggestion",
    "KPISuggestResponse",
    # Saved configs
    "SavedKPIConfig",
]
