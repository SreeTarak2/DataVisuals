"""
KPI Definitions
===============
Pre-built financial KPI definitions for all supported domains.
Includes: SaaS, E-commerce, Finance, Healthcare, Real Estate, HR,
Marketing, Education, Manufacturing, Logistics.
"""

from db.schemas_kpi import (
    KPICategory,
    AggregationType,
    TrendDirection,
    ComparisonPeriod,
    KPIDefinition,
    KPIFormula,
    KPIThreshold,
)

# ── New Enums for additional domains ─────────────────────────────────────────────
# Extends KPICategory with new domain-specific values if they exist.
# If not, we pass the raw string representation referenced elsewhere.

try:
    _HEALTHCARE = KPICategory("healthcare")
except ValueError:
    _HEALTHCARE = "healthcare"

try:
    _REAL_ESTATE = KPICategory("real_estate")
except ValueError:
    _REAL_ESTATE = "real_estate"

try:
    _HR_DOMAIN = KPICategory("hr")
except ValueError:
    _HR_DOMAIN = "hr"

try:
    _MARKETING = KPICategory("marketing")
except ValueError:
    _MARKETING = "marketing"

try:
    _EDUCATION = KPICategory("education")
except ValueError:
    _EDUCATION = "education"

try:
    _MANUFACTURING = KPICategory("manufacturing")
except ValueError:
    _MANUFACTURING = "manufacturing"

try:
    _LOGISTICS = KPICategory("logistics")
except ValueError:
    _LOGISTICS = "logistics"

try:
    _AUTOMOTIVE = KPICategory("automotive")
except ValueError:
    _AUTOMOTIVE = "automotive"


# ── SaaS ─────────────────────────────────────────────────────────────────────────

SAAS_KPIS: dict[str, KPIDefinition] = {
    "mrr": KPIDefinition(
        id="mrr",
        name="Monthly Recurring Revenue",
        description="Total predictable revenue per month from subscriptions",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "arr": KPIDefinition(
        id="arr",
        name="Annual Recurring Revenue",
        description="MRR × 12 - annualized recurring revenue",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="custom", custom_expression="mrr * 12"),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "churn_rate": KPIDefinition(
        id="churn_rate",
        name="Churn Rate",
        description="Percentage of customers lost during the period",
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
    ),
    "ltv": KPIDefinition(
        id="ltv",
        name="Customer Lifetime Value",
        description="Average revenue generated per customer over their lifetime",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="custom",
            custom_expression="(average_revenue_per_user / (churn_rate / 100))",
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="users",
        color="blue",
    ),
    "cac": KPIDefinition(
        id="cac",
        name="Customer Acquisition Cost",
        description="Total marketing spend / new customers acquired",
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
    ),
    "ltv_cac_ratio": KPIDefinition(
        id="ltv_cac_ratio",
        name="LTV/CAC Ratio",
        description="Return on customer acquisition investment (target: 3:1)",
        category=KPICategory.SAAS,
        formula=KPIFormula(formula_type="custom", custom_expression="ltv / cac"),
        format="number",
        decimals=1,
        suffix=":1",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=2.0, critical_min=1.0),
        icon="scale",
        color="purple",
    ),
    "nrr": KPIDefinition(
        id="nrr",
        name="Net Revenue Retention",
        description="Revenue from existing customers including expansions minus churn",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="growth", comparison_period=ComparisonPeriod.MONTH
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=100.0, critical_min=90.0),
        icon="refresh-cw",
        color="teal",
    ),
    "burn_rate": KPIDefinition(
        id="burn_rate",
        name="Monthly Burn Rate",
        description="Net cash consumed per month (expenses - revenue)",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="custom", custom_expression="total_expenses - total_revenue"
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="flame",
        color="red",
    ),
    "runway": KPIDefinition(
        id="runway",
        name="Cash Runway",
        description="Months of operation remaining at current burn rate",
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
    ),
    "arpu": KPIDefinition(
        id="arpu",
        name="Average Revenue Per User",
        description="Total revenue divided by number of active customers",
        category=KPICategory.SAAS,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="user",
        color="blue",
    ),
}


# ── E-commerce ───────────────────────────────────────────────────────────────────

ECOMMERCE_KPIS: dict[str, KPIDefinition] = {
    "total_revenue": KPIDefinition(
        id="total_revenue",
        name="Total Revenue",
        description="Sum of all sales revenue",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(formula_type="simple", column="revenue", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="shopping-cart",
        color="green",
    ),
    "aov": KPIDefinition(
        id="aov",
        name="Average Order Value",
        description="Average revenue per transaction",
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
    ),
    "order_count": KPIDefinition(
        id="order_count",
        name="Total Orders",
        description="Number of completed orders",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="package",
        color="purple",
    ),
    "gross_margin": KPIDefinition(
        id="gross_margin",
        name="Gross Margin",
        description="(Revenue - COGS) / Revenue × 100",
        category=KPICategory.ECOMMERCE,
        formula=KPIFormula(
            formula_type="custom",
            custom_expression="((revenue - cogs) / revenue) * 100",
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
}


# ── Finance ──────────────────────────────────────────────────────────────────────

FINANCE_KPIS: dict[str, KPIDefinition] = {
    "gross_profit": KPIDefinition(
        id="gross_profit",
        name="Gross Profit",
        description="Revenue minus cost of goods sold",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="custom", custom_expression="revenue - cogs"),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "net_profit": KPIDefinition(
        id="net_profit",
        name="Net Profit",
        description="Total profit after all expenses and taxes",
        category=KPICategory.FINANCE,
        formula=KPIFormula(
            formula_type="custom", custom_expression="revenue - total_expenses"
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "operating_expenses": KPIDefinition(
        id="operating_expenses",
        name="Operating Expenses",
        description="Total operational costs",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="credit-card",
        color="red",
    ),
    "net_cash_flow": KPIDefinition(
        id="net_cash_flow",
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
    ),
    "ar_aging": KPIDefinition(
        id="ar_aging",
        name="AR Aging (Days)",
        description="Average days outstanding for accounts receivable",
        category=KPICategory.FINANCE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" days",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=45.0, critical_max=90.0),
        icon="calendar",
        color="orange",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# NEW DOMAINS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Healthcare ───────────────────────────────────────────────────────────────────

HEALTHCARE_KPIS: dict[str, KPIDefinition] = {
    "total_treatment_cost": KPIDefinition(
        id="total_treatment_cost",
        name="Total Treatment Cost",
        description="Sum of all treatment-related costs",
        category=_HEALTHCARE,
        formula=KPIFormula(formula_type="simple", column="cost", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "avg_cost_per_patient": KPIDefinition(
        id="avg_cost_per_patient",
        name="Avg Cost per Patient",
        description="Average treatment cost per patient",
        category=_HEALTHCARE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_column="cost",
            numerator_aggregation=AggregationType.SUM,
            denominator_column="patient_id",
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="activity",
        color="blue",
    ),
    "avg_length_of_stay": KPIDefinition(
        id="avg_length_of_stay",
        name="Avg Length of Stay",
        description="Average days patients stay admitted",
        category=_HEALTHCARE,
        formula=KPIFormula(formula_type="simple", column="length_of_stay", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" days",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="clock",
        color="orange",
    ),
    "readmission_rate": KPIDefinition(
        id="readmission_rate",
        name="Readmission Rate",
        description="Percentage of patients readmitted",
        category=_HEALTHCARE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=15.0, critical_max=20.0),
        icon="user-minus",
        color="red",
    ),
    "patient_volume": KPIDefinition(
        id="patient_volume",
        name="Patient Volume",
        description="Total number of patients treated",
        category=_HEALTHCARE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="users",
        color="purple",
    ),
    "medication_count_avg": KPIDefinition(
        id="medication_count_avg",
        name="Avg Medications per Patient",
        description="Average number of medications prescribed per patient",
        category=_HEALTHCARE,
        formula=KPIFormula(formula_type="simple", column="quantity", aggregation=AggregationType.MEAN),
        format="number",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="package",
        color="teal",
    ),
}


# ── Real Estate ──────────────────────────────────────────────────────────────────

REAL_ESTATE_KPIS: dict[str, KPIDefinition] = {
    "avg_sale_price": KPIDefinition(
        id="avg_sale_price",
        name="Avg Sale Price",
        description="Average sale price of properties",
        category=_REAL_ESTATE,
        formula=KPIFormula(formula_type="simple", column="price", aggregation=AggregationType.MEAN),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "total_sales_volume": KPIDefinition(
        id="total_sales_volume",
        name="Total Sales Volume",
        description="Sum of all property sale prices",
        category=_REAL_ESTATE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "days_on_market": KPIDefinition(
        id="days_on_market",
        name="Avg Days on Market",
        description="Average days properties stay listed before selling",
        category=_REAL_ESTATE,
        formula=KPIFormula(formula_type="simple", column="days_on_market", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" days",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="clock",
        color="orange",
    ),
    "price_per_sqft": KPIDefinition(
        id="price_per_sqft",
        name="Price per Sq Ft",
        description="Average sale price per square foot",
        category=_REAL_ESTATE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.SUM,
        ),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="target",
        color="blue",
    ),
    "listing_count": KPIDefinition(
        id="listing_count",
        name="Total Listings",
        description="Number of property listings",
        category=_REAL_ESTATE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="home",
        color="purple",
    ),
    "avg_bedrooms": KPIDefinition(
        id="avg_bedrooms",
        name="Avg Bedrooms",
        description="Average number of bedrooms across properties",
        category=_REAL_ESTATE,
        formula=KPIFormula(formula_type="simple", column="bedrooms", aggregation=AggregationType.MEAN),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="package",
        color="teal",
    ),
}


# ── HR ───────────────────────────────────────────────────────────────────────────

HR_KPIS: dict[str, KPIDefinition] = {
    "total_salary_cost": KPIDefinition(
        id="total_salary_cost",
        name="Total Salary Cost",
        description="Sum of all employee salaries",
        category=_HR_DOMAIN,
        formula=KPIFormula(formula_type="simple", column="salary", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="dollar-sign",
        color="red",
    ),
    "avg_salary": KPIDefinition(
        id="avg_salary",
        name="Avg Salary",
        description="Average employee salary",
        category=_HR_DOMAIN,
        formula=KPIFormula(formula_type="simple", column="salary", aggregation=AggregationType.MEAN),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "headcount": KPIDefinition(
        id="headcount",
        name="Headcount",
        description="Total number of employees",
        category=_HR_DOMAIN,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="users",
        color="blue",
    ),
    "turnover_rate": KPIDefinition(
        id="turnover_rate",
        name="Employee Turnover Rate",
        description="Percentage of employees who left",
        category=_HR_DOMAIN,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=15.0, critical_max=25.0),
        icon="user-minus",
        color="red",
    ),
    "avg_tenure": KPIDefinition(
        id="avg_tenure",
        name="Avg Employee Tenure",
        description="Average years employees stay at company",
        category=_HR_DOMAIN,
        formula=KPIFormula(formula_type="simple", column="tenure", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" years",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="clock",
        color="purple",
    ),
    "avg_performance_score": KPIDefinition(
        id="avg_performance_score",
        name="Avg Performance Score",
        description="Average employee performance rating",
        category=_HR_DOMAIN,
        formula=KPIFormula(formula_type="simple", column="performance", aggregation=AggregationType.MEAN),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="target",
        color="teal",
    ),
}


# ── Marketing ─────────────────────────────────────────────────────────────────────

MARKETING_KPIS: dict[str, KPIDefinition] = {
    "total_spend": KPIDefinition(
        id="total_spend",
        name="Total Marketing Spend",
        description="Sum of all marketing/advertising spend",
        category=_MARKETING,
        formula=KPIFormula(formula_type="simple", column="cost", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="credit-card",
        color="red",
    ),
    "total_revenue_marketing": KPIDefinition(
        id="total_revenue_marketing",
        name="Marketing Revenue",
        description="Revenue attributed to marketing efforts",
        category=_MARKETING,
        formula=KPIFormula(formula_type="simple", column="revenue", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "roas": KPIDefinition(
        id="roas",
        name="Return on Ad Spend",
        description="Revenue divided by ad spend",
        category=_MARKETING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.SUM,
        ),
        format="number",
        suffix="x",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=2.0, critical_min=1.0),
        icon="target",
        color="purple",
    ),
    "conversion_rate": KPIDefinition(
        id="conversion_rate_marketing",
        name="Conversion Rate",
        description="Percentage of interactions that converted",
        category=_MARKETING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "total_impressions": KPIDefinition(
        id="total_impressions",
        name="Total Impressions",
        description="Total number of ad/content views",
        category=_MARKETING,
        formula=KPIFormula(formula_type="simple", column="impressions", aggregation=AggregationType.SUM),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="activity",
        color="blue",
    ),
    "total_clicks": KPIDefinition(
        id="total_clicks",
        name="Total Clicks",
        description="Total number of ad/content clicks",
        category=_MARKETING,
        formula=KPIFormula(formula_type="simple", column="clicks", aggregation=AggregationType.SUM),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="mouse-pointer",
        color="teal",
    ),
    "cpc": KPIDefinition(
        id="cpc",
        name="Cost Per Click",
        description="Average cost of each click",
        category=_MARKETING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.SUM,
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="target",
        color="orange",
    ),
}


# ── Education ─────────────────────────────────────────────────────────────────────

EDUCATION_KPIS: dict[str, KPIDefinition] = {
    "enrollment_count": KPIDefinition(
        id="enrollment_count",
        name="Total Enrollment",
        description="Total number of enrolled students",
        category=_EDUCATION,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="users",
        color="blue",
    ),
    "avg_gpa": KPIDefinition(
        id="avg_gpa",
        name="Average GPA",
        description="Average grade point average across students",
        category=_EDUCATION,
        formula=KPIFormula(formula_type="simple", column="gpa", aggregation=AggregationType.MEAN),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="target",
        color="green",
    ),
    "avg_grade": KPIDefinition(
        id="avg_grade",
        name="Average Grade",
        description="Average test/exam score",
        category=_EDUCATION,
        formula=KPIFormula(formula_type="simple", column="grade", aggregation=AggregationType.MEAN),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="purple",
    ),
    "graduation_rate": KPIDefinition(
        id="graduation_rate",
        name="Graduation Rate",
        description="Percentage of students who graduated",
        category=_EDUCATION,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=70.0, critical_min=50.0),
        icon="user-check",
        color="teal",
    ),
    "attendance_rate": KPIDefinition(
        id="attendance_rate",
        name="Attendance Rate",
        description="Percentage of classes attended",
        category=_EDUCATION,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=80.0, critical_min=60.0),
        icon="calendar",
        color="orange",
    ),
}


# ── Manufacturing ────────────────────────────────────────────────────────────────

MANUFACTURING_KPIS: dict[str, KPIDefinition] = {
    "total_units_produced": KPIDefinition(
        id="total_units_produced",
        name="Total Units Produced",
        description="Sum of all units produced",
        category=_MANUFACTURING,
        formula=KPIFormula(formula_type="simple", column="quantity", aggregation=AggregationType.SUM),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="package",
        color="green",
    ),
    "defect_count": KPIDefinition(
        id="defect_count",
        name="Total Defects",
        description="Number of defective units",
        category=_MANUFACTURING,
        formula=KPIFormula(formula_type="simple", column="defect", aggregation=AggregationType.SUM),
        format="number",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="alert-triangle",
        color="red",
    ),
    "defect_rate": KPIDefinition(
        id="defect_rate",
        name="Defect Rate",
        description="Defects as percentage of total units",
        category=_MANUFACTURING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        thresholds=KPIThreshold(warning_max=5.0, critical_max=10.0),
        icon="activity",
        color="red",
    ),
    "yield_rate": KPIDefinition(
        id="yield_rate",
        name="Yield Rate",
        description="Percentage of units that pass quality inspection",
        category=_MANUFACTURING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=90.0, critical_min=80.0),
        icon="target",
        color="green",
    ),
    "avg_cycle_time": KPIDefinition(
        id="avg_cycle_time",
        name="Avg Cycle Time",
        description="Average production cycle time",
        category=_MANUFACTURING,
        formula=KPIFormula(formula_type="simple", column="cycle_time", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" hrs",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="clock",
        color="orange",
    ),
    "total_cost_manufacturing": KPIDefinition(
        id="total_cost_manufacturing",
        name="Total Production Cost",
        description="Sum of all production-related costs",
        category=_MANUFACTURING,
        formula=KPIFormula(formula_type="simple", column="cost", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="dollar-sign",
        color="red",
    ),
    "cost_per_unit": KPIDefinition(
        id="cost_per_unit",
        name="Cost per Unit",
        description="Average production cost per unit",
        category=_MANUFACTURING,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="target",
        color="orange",
    ),
}


# ── Logistics ─────────────────────────────────────────────────────────────────────

LOGISTICS_KPIS: dict[str, KPIDefinition] = {
    "total_shipping_cost": KPIDefinition(
        id="total_shipping_cost",
        name="Total Shipping Cost",
        description="Sum of all shipping costs",
        category=_LOGISTICS,
        formula=KPIFormula(formula_type="simple", column="cost", aggregation=AggregationType.SUM),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="dollar-sign",
        color="red",
    ),
    "shipment_volume": KPIDefinition(
        id="shipment_volume",
        name="Shipment Volume",
        description="Total number of shipments",
        category=_LOGISTICS,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="package",
        color="blue",
    ),
    "avg_delivery_time": KPIDefinition(
        id="avg_delivery_time",
        name="Avg Delivery Time",
        description="Average shipping delivery time",
        category=_LOGISTICS,
        formula=KPIFormula(formula_type="simple", column="delivery_time", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" days",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="clock",
        color="orange",
    ),
    "cost_per_mile": KPIDefinition(
        id="cost_per_mile",
        name="Cost per Mile/Km",
        description="Average shipping cost per unit distance",
        category=_LOGISTICS,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.SUM,
            denominator_aggregation=AggregationType.SUM,
        ),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="target",
        color="purple",
    ),
    "on_time_rate": KPIDefinition(
        id="on_time_rate",
        name="On-Time Delivery Rate",
        description="Percentage of shipments delivered on time",
        category=_LOGISTICS,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        thresholds=KPIThreshold(warning_min=90.0, critical_min=80.0),
        icon="trending-up",
        color="green",
    ),
    "total_weight": KPIDefinition(
        id="total_weight",
        name="Total Shipment Weight",
        description="Sum of all shipment weights",
        category=_LOGISTICS,
        formula=KPIFormula(formula_type="simple", column="weight", aggregation=AggregationType.SUM),
        format="number",
        suffix=" kg",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="scale",
        color="teal",
    ),
    "total_distance": KPIDefinition(
        id="total_distance",
        name="Total Distance",
        description="Sum of all shipping distances",
        category=_LOGISTICS,
        formula=KPIFormula(formula_type="simple", column="distance", aggregation=AggregationType.SUM),
        format="number",
        suffix=" km",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="activity",
        color="blue",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Combined Registry — used by KPIService and IntelligentKPIGenerator
# ═══════════════════════════════════════════════════════════════════════════════


# ── Automotive ───────────────────────────────────────────────────────────────────

AUTOMOTIVE_KPIS: dict[str, KPIDefinition] = {
    "avg_price": KPIDefinition(
        id="avg_price",
        name="Average Price",
        description="Average listing price of vehicles",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="price", aggregation=AggregationType.MEAN),
        format="currency",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="dollar-sign",
        color="green",
    ),
    "avg_mileage": KPIDefinition(
        id="avg_mileage",
        name="Average Mileage",
        description="Average odometer reading of vehicles",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="mileage", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" miles",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="activity",
        color="orange",
    ),
    "listing_count": KPIDefinition(
        id="listing_count",
        name="Total Listings",
        description="Number of vehicle listings in dataset",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", aggregation=AggregationType.COUNT),
        format="number",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="package",
        color="blue",
    ),
    "avg_engine_size": KPIDefinition(
        id="avg_engine_size",
        name="Avg Engine Size",
        description="Average engine displacement across vehicles",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="engine_size", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" L",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="target",
        color="purple",
    ),
    "avg_mpg": KPIDefinition(
        id="avg_mpg",
        name="Average MPG",
        description="Average miles per gallon across vehicles",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="mpg", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" mpg",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="trending-up",
        color="green",
    ),
    "oldest_year": KPIDefinition(
        id="oldest_year",
        name="Oldest Vehicle Year",
        description="Model year of the oldest vehicle",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="year", aggregation=AggregationType.MIN),
        format="number",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="calendar",
        color="red",
    ),
    "avg_horsepower": KPIDefinition(
        id="avg_horsepower",
        name="Avg Horsepower",
        description="Average engine power output",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="horsepower", aggregation=AggregationType.MEAN),
        format="number",
        suffix=" hp",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="zap",
        color="amber",
    ),
    "avg_tax": KPIDefinition(
        id="avg_tax",
        name="Average Annual Tax",
        description="Average annual road tax",
        category=_AUTOMOTIVE,
        formula=KPIFormula(formula_type="simple", column="tax", aggregation=AggregationType.MEAN),
        format="currency",
        trend_direction=TrendDirection.DOWN_IS_GOOD,
        icon="credit-card",
        color="red",
    ),
    "fuel_type_distribution": KPIDefinition(
        id="fuel_type_distribution",
        name="Fuel Type Distribution",
        description="Distribution of vehicles by fuel type",
        category=_AUTOMOTIVE,
        formula=KPIFormula(
            formula_type="ratio",
            numerator_aggregation=AggregationType.COUNT,
            denominator_aggregation=AggregationType.COUNT,
        ),
        format="percentage",
        trend_direction=TrendDirection.UP_IS_GOOD,
        icon="activity",
        color="teal",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Combined Registry — used by KPIService and IntelligentKPIGenerator
# ═══════════════════════════════════════════════════════════════════════════════

ALL_KPIS: dict[str, KPIDefinition] = {
    **SAAS_KPIS,
    **ECOMMERCE_KPIS,
    **FINANCE_KPIS,
    **HEALTHCARE_KPIS,
    **REAL_ESTATE_KPIS,
    **HR_KPIS,
    **MARKETING_KPIS,
    **EDUCATION_KPIS,
    **MANUFACTURING_KPIS,
    **LOGISTICS_KPIS,
    **AUTOMOTIVE_KPIS,
}
